import asyncio
import gpiod
import aiomqtt
import json
import logging
import os
from functools import partial

# --- Setup Logging (early, for config errors) ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# --- Load Configuration ---
CONFIG_FILE = os.environ.get("GPIO_CONFIG", "config.json")

try:
    with open(CONFIG_FILE) as f:
        config = json.load(f)
except FileNotFoundError:
    logger.error(f"Configuration file '{CONFIG_FILE}' not found. Please create it or set GPIO_CONFIG env var.")
    raise SystemExit(1)
except json.JSONDecodeError as e:
    logger.error(f"Configuration file '{CONFIG_FILE}' contains invalid JSON: {e}")
    raise SystemExit(1)
except PermissionError:
    logger.error(f"Permission denied reading configuration file '{CONFIG_FILE}'.")
    raise SystemExit(1)

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
output_lines = {}
publish_queue = asyncio.Queue()

def get_topic(chip: int, pin: int) -> str:
    return f"{GPIO_BASE_TOPIC}/gpiochip{chip}/{pin}"

def handle_gpio_event(line, chip, pin):
    """
    Triggered instantly by the asyncio event loop when the file descriptor has data.
    Puts the event into a queue so it doesn't block, and survives MQTT drops.
    """
    try:
        event = line.event_read()
        # 1 for RISING_EDGE (High), 0 for FALLING_EDGE (Low)
        state = "1" if event.type == gpiod.LineEvent.RISING_EDGE else "0"
        topic = get_topic(chip, pin)

        # Add to async queue instead of publishing directly
        publish_queue.put_nowait((topic, state))
        logger.info(f"Input triggered: gpiochip{chip} pin {pin} -> {state}")
    except Exception as e:
        logger.error(f"Error reading GPIO event: {e}")

def init_hardware(loop):
    """Initializes libgpiod bindings and hooks inputs into the async loop."""
    logger.info("Initializing libgpiod hardware...")
    
    # Configure Outputs
    for cfg in OUTPUT_PINS:
        chip_no = cfg["gpiochip"]
        pin_no = cfg["pin"]
        chip = gpiod.Chip(f"gpiochip{chip_no}")
        line = chip.get_line(pin_no)
        line.request(consumer="mqtt_bridge_out", type=gpiod.LINE_REQ_DIR_OUT)
        
        # Store for later modification
        output_lines[f"{chip_no}_{pin_no}"] = line
        logger.info(f"Configured OUTPUT: gpiochip{chip_no} pin {pin_no}")

    # Configure Inputs
    for cfg in INPUT_PINS:
        chip_no = cfg["gpiochip"]
        pin_no = cfg["pin"]
        chip = gpiod.Chip(f"gpiochip{chip_no}")
        line = chip.get_line(pin_no)
        line.request(consumer="mqtt_bridge_in", type=gpiod.LINE_REQ_EV_BOTH_EDGES)
        
        # Extract the Linux File Descriptor for this pin
        fd = line.event_get_fd()
        
        # Bind the FD directly to Python's asyncio loop! No threads needed.
        callback = partial(handle_gpio_event, line, chip_no, pin_no)
        loop.add_reader(fd, callback)
        logger.info(f"Configured INPUT via Async FD: gpiochip{chip_no} pin {pin_no}")

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
                        dict_key = f"{chip_str}_{pin_str}"

                        if dict_key in output_lines:
                            line = output_lines[dict_key]
                            val = 1 if payload in ["1", "ON", "true"] else 0

                            # Set the physical GPIO pin via libgpiod
                            line.set_value(val)

                            # Publish the state back to HA
                            state_topic = get_topic(chip_str, pin_str)
                            await mqtt_client.publish(state_topic, str(val))
                            logger.info(f"MQTT Command -> Set gpiochip{chip_str} pin {pin_str} to {val}")

        except aiomqtt.MqttError as error:
            logger.warning(f"MQTT disconnected: {error}. Retrying in 10 s...")
            await asyncio.sleep(10)
            # Worker task gets cancelled on drop, will restart on reconnect.

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down cleanly.")