"""Mobile device presets for viewport emulation."""

DEVICE_PRESETS = {
    # iPhones
    "iphone_14": {
        "name": "iPhone 14",
        "width": 390,
        "height": 844,
        "device_scale_factor": 3,
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    },
    "iphone_14_pro_max": {
        "name": "iPhone 14 Pro Max",
        "width": 430,
        "height": 932,
        "device_scale_factor": 3,
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    },
    "iphone_15": {
        "name": "iPhone 15",
        "width": 393,
        "height": 852,
        "device_scale_factor": 3,
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
    },
    "iphone_se": {
        "name": "iPhone SE",
        "width": 375,
        "height": 667,
        "device_scale_factor": 2,
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    },
    # iPads
    "ipad_pro_12": {
        "name": 'iPad Pro 12.9"',
        "width": 1024,
        "height": 1366,
        "device_scale_factor": 2,
        "user_agent": "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    },
    "ipad_pro_11": {
        "name": 'iPad Pro 11"',
        "width": 834,
        "height": 1194,
        "device_scale_factor": 2,
        "user_agent": "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    },
    "ipad_mini": {
        "name": "iPad Mini",
        "width": 768,
        "height": 1024,
        "device_scale_factor": 2,
        "user_agent": "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    },
    # Android phones
    "pixel_7": {
        "name": "Google Pixel 7",
        "width": 412,
        "height": 915,
        "device_scale_factor": 2.625,
        "user_agent": "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36",
    },
    "pixel_8_pro": {
        "name": "Google Pixel 8 Pro",
        "width": 448,
        "height": 998,
        "device_scale_factor": 2.5,
        "user_agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36",
    },
    "samsung_s24": {
        "name": "Samsung Galaxy S24",
        "width": 360,
        "height": 780,
        "device_scale_factor": 3,
        "user_agent": "Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36",
    },
    "samsung_s24_ultra": {
        "name": "Samsung Galaxy S24 Ultra",
        "width": 412,
        "height": 915,
        "device_scale_factor": 3,
        "user_agent": "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36",
    },
    "samsung_fold": {
        "name": "Samsung Galaxy Z Fold 5",
        "width": 373,
        "height": 841,
        "device_scale_factor": 3,
        "user_agent": "Mozilla/5.0 (Linux; Android 14; SM-F946B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36",
    },
    # Android tablets
    "samsung_tab_s9": {
        "name": "Samsung Galaxy Tab S9",
        "width": 800,
        "height": 1280,
        "device_scale_factor": 2,
        "user_agent": "Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Safari/537.36",
    },
    # Desktop presets
    "macbook_pro_16": {
        "name": 'MacBook Pro 16"',
        "width": 1728,
        "height": 1117,
        "device_scale_factor": 2,
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    },
    "desktop_1080p": {
        "name": "Desktop 1080p",
        "width": 1920,
        "height": 1080,
        "device_scale_factor": 1,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    },
    "desktop_1440p": {
        "name": "Desktop 1440p",
        "width": 2560,
        "height": 1440,
        "device_scale_factor": 1,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    },
}


def get_device_preset(device_name: str | None) -> dict | None:
    """Get a device preset by name. Returns None if not found."""
    if not device_name:
        return None
    return DEVICE_PRESETS.get(device_name.lower().replace(" ", "_").replace("-", "_"))


def list_device_presets() -> list[dict]:
    """List all available device presets."""
    return [
        {
            "id": key,
            "name": preset["name"],
            "width": preset["width"],
            "height": preset["height"],
            "type": (
                "phone"
                if preset["width"] <= 430
                else "tablet"
                if preset["width"] <= 1024
                else "desktop"
            ),
        }
        for key, preset in DEVICE_PRESETS.items()
    ]
