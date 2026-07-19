import asyncio
import gpiod
from gpiod.line import Direction, Value, Edge
import aiomqtt
import json
import logging
import os
from functools import partial

# --- Setup Logging (early, for config errors) ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Load Configuration ---
CONFIG_FILE = os.environ.get("GPIO_CONFIG", "config.json")

with open(CONFIG_FILE) as f:
    config = json.load(f)

MQTT_BROKER = config.get("mqtt", {}).get("broker")
if not MQTT_BROKER:
    logger.error("Missing required 'mqtt.broker' in configuration.")
    raise SystemExit(1)

MQTT_PORT = config.get("mqtt", {}).get("port", 1883)
MQTT_USER = config.get("mqtt", {}).get("username", "")
MQTT_PASS = config.get("mqtt", {}).get("password", "")

GPIO_BASE_TOPIC = config.get("gpio", {}).get("base_topic", "orangepi/gpio")
INPUT_PINS = config.get("gpio", {}).get("input_pins", [])
OUTPUT_PINS = config.get("gpio", {}).get("output_pins", [])

# Global state mapping
output_requests = {}
publish_queue = asyncio.Queue()

# Create lookup dictionaries for pin settings
output_pin_settings = {}
for cfg in OUTPUT_PINS:
    key = f"{cfg['gpiochip']}_{cfg['pin']}"
    output_pin_settings[key] = {
        "default_state": cfg.get("default_state", 0),
        "invert": cfg.get("invert", False)
    }

input_pin_settings = {}
for cfg in INPUT_PINS:
    key = f"{cfg['gpiochip']}_{cfg['pin']}"
    input_pin_settings[key] = {
        "invert": cfg.get("invert", False)
    }

def get_topic(chip: int, pin: int) -> str:
    return f"{GPIO_BASE_TOPIC}/gpiochip{chip}/{pin}"


def handle_gpio_event(req, chip, pin, invert):
    """
    Triggered instantly by the asyncio event loop when the file descriptor has data.
    Reads v2 edge events and queues them for MQTT publication.
    """
    try:
        # v2 API reads all pending events as a list
        for event in req.read_edge_events():
            # Check the string representation of the Enum for RISING/FALLING
            state = "1" if "RISING" in str(event.event_type) else "0"
            
            # Apply inversion if configured
            if invert:
                state = "1" if state == "0" else "0"
            
            topic = get_topic(chip, pin)
            publish_queue.put_nowait((topic, state))
            logger.info(f"Input triggered: gpiochip{chip} pin {pin} -> {state}")
    except Exception as e:
        logger.error(f"Error reading GPIO event: {e}")

def init_hardware(loop):
    """Initializes libgpiod v2 bindings and hooks inputs into the async loop."""
    logger.info("Initializing libgpiod v2 hardware...")
    
    # Configure Outputs
    for cfg in OUTPUT_PINS:
        chip_no = cfg["gpiochip"]
        pin_no = cfg["pin"]
        key = f"{chip_no}_{pin_no}"
        settings = output_pin_settings[key]
        default_state = settings["default_state"]
        invert = settings["invert"]
        
        # Apply inversion to the initial state if configured
        physical_init_value = 1 - default_state if invert else default_state
        init_val = Value.ACTIVE if physical_init_value == 1 else Value.INACTIVE
        
        req = gpiod.request_lines(
            f"/dev/gpiochip{chip_no}",
            consumer="mqtt_bridge_out",
            config={
                pin_no: gpiod.LineSettings(
                    direction=Direction.OUTPUT, output_value=init_val
                )
            }
        )
        
        # Store the LineRequest object, not a Line
        output_requests[key] = req
        logger.info(f"Configured OUTPUT: gpiochip{chip_no} pin {pin_no} -> {default_state} (physical: {physical_init_value}, invert: {invert})")

    # Configure Inputs
    for cfg in INPUT_PINS:
        chip_no = cfg["gpiochip"]
        pin_no = cfg["pin"]
        key = f"{chip_no}_{pin_no}"
        settings = input_pin_settings[key]
        invert = settings["invert"]
        
        req = gpiod.request_lines(
            f"/dev/gpiochip{chip_no}",
            consumer="mqtt_bridge_in",
            config={
                pin_no: gpiod.LineSettings(
                    direction=Direction.INPUT, edge_detection=Edge.BOTH
                )
            }
        )
        
        # The LineRequest object exposes the file descriptor directly
        fd = req.fd
        
        # Bind the FD directly to Python's asyncio loop
        callback = partial(handle_gpio_event, req, chip_no, pin_no, invert)
        loop.add_reader(fd, callback)
        logger.info(f"Configured INPUT via Async FD: gpiochip{chip_no} pin {pin_no} (invert: {invert})")

async def queue_worker(mqtt_client):
    """Reads from the internal queue and publishes to MQTT."""
    while True:
        topic, payload = await publish_queue.get()
        await mqtt_client.publish(topic, payload)
        publish_queue.task_done()

async def publish_discovery(mqtt_client, output_pins: list[dict], input_pins: list[dict]) -> None:
    """Publishes MQTT Auto-Discovery payloads so Home Assistant sees the pins automatically."""
    for cfg in output_pins:
        chip, pin = cfg["gpiochip"], cfg["pin"]
        name = cfg.get("name", f"gpio_{chip}_{pin}")
        topic = get_topic(chip, pin)

        discovery_topic = f"homeassistant/switch/orangepi_gpio_{chip}_{pin}/config"
        payload = {
            "name": name,
            "unique_id": f"opi_gpio_{chip}_{pin}",
            "command_topic": f"{topic}/set",
            "state_topic": topic,
            "payload_on": "1",
            "payload_off": "0",
        }
        await mqtt_client.publish(
            discovery_topic, payload=json.dumps(payload), retain=True
        )

    for cfg in input_pins:
        chip, pin = cfg["gpiochip"], cfg["pin"]
        name = cfg.get("name", f"gpio_{chip}_{pin}")
        topic = get_topic(chip, pin)

        discovery_topic = (
            f"homeassistant/binary_sensor/orangepi_gpio_{chip}_{pin}/config"
        )
        payload = {
            "name": name,
            "unique_id": f"opi_input_{chip}_{pin}",
            "state_topic": topic,
            "payload_on": "1",
            "payload_off": "0",
        }
        await mqtt_client.publish(
            discovery_topic, payload=json.dumps(payload), retain=True
        )
    logger.info("Published Home Assistant Auto-Discovery payloads.")

async def main():
    loop = asyncio.get_running_loop()

    # Initialize GPIO *once* so lines aren't locked if MQTT drops
    init_hardware(loop)

    # Universal Reconnection Loop
    while True:
        try:
            logger.info(f"Attempting to connect to MQTT at {MQTT_BROKER}...")
            async with aiomqtt.Client(
                hostname=MQTT_BROKER,
                port=MQTT_PORT,
                username=MQTT_USER,
                password=MQTT_PASS
            ) as mqtt_client:
                logger.info("Connected to MQTT broker.")

                # Start background task to drain the publish queue
                asyncio.create_task(queue_worker(mqtt_client))

                # Publish HA discovery configs
                await publish_discovery(mqtt_client, OUTPUT_PINS, INPUT_PINS)

                # Subscribe to all output command topics dynamically
                await mqtt_client.subscribe(f"{GPIO_BASE_TOPIC}/+/+/set")

                # Listen for incoming MQTT commands to change output pins
                async for message in mqtt_client.messages:
                    topic = message.topic.value
                    payload = message.payload.decode("utf-8")

                    parts = topic.split('/')
                    
                    if len(parts) == 5 and parts[-1] == "set":
                        chip_str = parts[2].replace("gpiochip", "")
                        pin_str = parts[3]
                        # Convert to int to match config format, then back to string for lookup key
                        chip_int = int(chip_str)
                        pin_int = int(pin_str)
                        dict_key = f"{chip_int}_{pin_int}"

                        if dict_key in output_requests:
                            req = output_requests[dict_key]
                            settings = output_pin_settings[dict_key]
                            invert = settings["invert"]
                            
                            # Parse desired logical state (0 or 1)
                            desired_logical = 1 if payload in ["1", "ON", "true"] else 0
                            
                            # Apply inversion if configured
                            physical_value = 1 - desired_logical if invert else desired_logical

                            # Convert to v2 Enum and set the physical GPIO pin
                            val_enum = Value.ACTIVE if physical_value == 1 else Value.INACTIVE
                            req.set_value(pin_int, val_enum)

                            # Publish the logical state back to HA
                            state_topic = get_topic(chip_str, pin_str)
                            await mqtt_client.publish(state_topic, str(desired_logical))
                            logger.info(f"MQTT Command -> Set gpiochip{chip_str} pin {pin_str} to {desired_logical} (physical: {physical_value}, invert: {invert})")

        except aiomqtt.MqttError as error:
            logger.warning(f"MQTT disconnected: {error}. Retrying in 10 s...")
            await asyncio.sleep(10)
            # Worker task gets cancelled on drop, will restart on reconnect.

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down cleanly.")