def map_ajax_device(device: dict) -> list[tuple[str, dict]]:
    """
    Maps an Ajax device to Home Assistant platforms.
    
    Returns:
        List of tuples: (platform, {device_class, unit, ...})
    """
    device_type = device.get("deviceType", "").lower()
    result = []

    if device_type in [
        "motionprotect", "motionprotectplus", "motionprotectoutdoor", "motionprotectcurtain"
    ]:
        result.append(("binary_sensor", {"device_class": "motion"}))
        result.append(("sensor", {"device_class": "motion_temperature", "unit": "°C"}))

    elif device_type in ["doorprotect", "doorprotectplus"]:
        result.append(("binary_sensor", {"device_class": "opening"}))
        result.append(("sensor", {"device_class": "door_temperature", "unit": "°C"}))

    elif device_type == "glassprotect":
        result.append(("binary_sensor", {"device_class": "sound"}))

    elif device_type == "combiprotect":
        result.append(("binary_sensor", {"device_class": "motion"}))
        result.append(("binary_sensor", {"device_class": "sound"}))

    elif device_type in ["fireprotect", "fireprotectplus"]:
        result.append(("binary_sensor", {"device_class": "smoke"}))
        result.append(("sensor", {"device_class": "temperature", "unit": "°C"}))
        #result.append(("sensor", {"device_class": "carbon_monoxide", "unit": "ppm"}))

    elif device_type == "leaksprotect":
        result.append(("binary_sensor", {"device_class": "moisture"}))

    elif device_type in ["homesiren", "streetsiren"]:
        result.append(("binary_sensor", {}))

    elif device_type in ["lifelinebutton", "button"]:
        result.append(("button", {"device_class": "restart"}))

    elif device_type == "doublebutton":
        result.append(("button", {"device_class": "update"}))

    elif device_type == "spacecontrol":
        result.append(("event", {"event_type": "ajax_remote"}))

    elif device_type in ["keypad", "keypadplus"]:
        result.append(("event", {"event_type": "ajax_keypad"}))

    elif device_type in ["wallswitch", "socket", "relay"]:
        result.append(("switch", {}))
        result.append(("sensor", {"device_class": "power", "unit": "W"}))
        result.append(("sensor", {"device_class": "energy", "unit": "kWh"}))

    elif device_type == "powersupply":
        result.append(("sensor", {"device_class": "voltage", "unit": "V"}))

    elif device_type in ["rex", "rex2"]:
        result.append(("binary_sensor", {"device_class": "connectivity"}))

    elif device_type == "lifequality":
        result.append(("sensor", {"device_class": "temperature", "unit": "°C"}))
        result.append(("sensor", {"device_class": "humidity", "unit": "%"}))
        result.append(("sensor", {"device_class": "carbon_dioxide", "unit": "ppm"}))

    elif device_type in ["transmitter", "multitransmitter"]:
        result.append(("binary_sensor", {"device_class": "generic"}))

    elif device_type in ["hub", "ajaxhub"]:
        result.append(("alarm_control_panel", {}))

    return result
