"""Create a URL change monitor with webhook notifications."""

from webharvest import DataBlue

wh = DataBlue(api_url="http://localhost:8000", api_key="wh_your_key_here")

# Create a monitor that checks a page every hour
monitor = wh.create_monitor(
    url="https://example.com/pricing",
    check_interval_minutes=60,
    css_selector=".pricing-table",  # Only monitor this section
    webhook_url="https://your-server.com/webhook",  # Get notified on changes
    keywords=["price", "discount", "sale"],  # Track these keywords
    threshold=0.95,  # Trigger on >5% content change
)

print(f"Monitor created: {monitor.get('id')}")
print(f"URL: {monitor.get('url')}")
print(f"Interval: {monitor.get('check_interval_minutes')} minutes")

# List all monitors
monitors = wh.list_monitors()
print(f"\nTotal monitors: {len(monitors.get('monitors', []))}")
for m in monitors.get("monitors", []):
    print(f"  - {m.get('url')} (status: {m.get('status', 'active')})")

wh.close()
