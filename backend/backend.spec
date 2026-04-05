# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('policy/policies.yaml', 'policy'), ('intent/rules/rules.yaml', 'intent/rules'), ('/Users/nohgiyoon/Coding/AI/Agent/frontend/out', 'frontend_out'), ('plugins/__init__.py', 'plugins'), ('plugins/calendar_helper/README.md', 'plugins/calendar_helper'), ('plugins/calendar_helper/ai_instructions.md', 'plugins/calendar_helper'), ('plugins/calendar_helper/plugin.json', 'plugins/calendar_helper'), ('plugins/calendar_helper/plugin.py', 'plugins/calendar_helper'), ('plugins/calendar_helper/rules.yaml', 'plugins/calendar_helper'), ('plugins/communication_helper/README.md', 'plugins/communication_helper'), ('plugins/communication_helper/ai_instructions.md', 'plugins/communication_helper'), ('plugins/communication_helper/plugin.json', 'plugins/communication_helper'), ('plugins/communication_helper/plugin.py', 'plugins/communication_helper'), ('plugins/communication_helper/rules.yaml', 'plugins/communication_helper'), ('plugins/delivery_helper/README.md', 'plugins/delivery_helper'), ('plugins/delivery_helper/ai_instructions.md', 'plugins/delivery_helper'), ('plugins/delivery_helper/plugin.json', 'plugins/delivery_helper'), ('plugins/delivery_helper/plugin.py', 'plugins/delivery_helper'), ('plugins/delivery_helper/rules.yaml', 'plugins/delivery_helper'), ('plugins/draft_helper/README.md', 'plugins/draft_helper'), ('plugins/draft_helper/ai_instructions.md', 'plugins/draft_helper'), ('plugins/draft_helper/plugin.json', 'plugins/draft_helper'), ('plugins/draft_helper/plugin.py', 'plugins/draft_helper'), ('plugins/draft_helper/rules.yaml', 'plugins/draft_helper'), ('plugins/example_echo/README.md', 'plugins/example_echo'), ('plugins/example_echo/ai_instructions.md', 'plugins/example_echo'), ('plugins/example_echo/plugin.json', 'plugins/example_echo'), ('plugins/example_echo/plugin.py', 'plugins/example_echo'), ('plugins/example_echo/rules.yaml', 'plugins/example_echo'), ('plugins/loader.py', 'plugins'), ('plugins/reminder_helper/ai_instructions.md', 'plugins/reminder_helper'), ('plugins/reminder_helper/plugin.json', 'plugins/reminder_helper'), ('plugins/reminder_helper/plugin.py', 'plugins/reminder_helper'), ('plugins/reminder_helper/rules.yaml', 'plugins/reminder_helper'), ('plugins/reservation_helper/README.md', 'plugins/reservation_helper'), ('plugins/reservation_helper/ai_instructions.md', 'plugins/reservation_helper'), ('plugins/reservation_helper/plugin.json', 'plugins/reservation_helper'), ('plugins/reservation_helper/plugin.py', 'plugins/reservation_helper'), ('plugins/reservation_helper/rules.yaml', 'plugins/reservation_helper'), ('plugins/route_helper/README.md', 'plugins/route_helper'), ('plugins/route_helper/ai_instructions.md', 'plugins/route_helper'), ('plugins/route_helper/plugin.json', 'plugins/route_helper'), ('plugins/route_helper/plugin.py', 'plugins/route_helper'), ('plugins/route_helper/rules.yaml', 'plugins/route_helper'), ('plugins/shopping_helper/ai_instructions.md', 'plugins/shopping_helper'), ('plugins/shopping_helper/plugin.json', 'plugins/shopping_helper'), ('plugins/shopping_helper/plugin.py', 'plugins/shopping_helper'), ('plugins/translation_helper/plugin.json', 'plugins/translation_helper'), ('plugins/translation_helper/plugin.py', 'plugins/translation_helper'), ('plugins/translation_helper/rules.yaml', 'plugins/translation_helper'), ('plugins/travel_helper/README.md', 'plugins/travel_helper'), ('plugins/travel_helper/ai_instructions.md', 'plugins/travel_helper'), ('plugins/travel_helper/plugin.json', 'plugins/travel_helper'), ('plugins/travel_helper/plugin.py', 'plugins/travel_helper'), ('plugins/travel_helper/rules.yaml', 'plugins/travel_helper'), ('plugins/weather_alert_helper/README.md', 'plugins/weather_alert_helper'), ('plugins/weather_alert_helper/ai_instructions.md', 'plugins/weather_alert_helper'), ('plugins/weather_alert_helper/plugin.json', 'plugins/weather_alert_helper'), ('plugins/weather_alert_helper/plugin.py', 'plugins/weather_alert_helper'), ('plugins/weather_alert_helper/rules.yaml', 'plugins/weather_alert_helper'), ('connections/__init__.py', 'connections'), ('connections/base.py', 'connections'), ('connections/drivers/__init__.py', 'connections/drivers'), ('connections/drivers/gmail.py', 'connections/drivers'), ('connections/drivers/google_calendar.py', 'connections/drivers'), ('connections/drivers/mcp_client.py', 'connections/drivers'), ('connections/drivers/template_connector.py', 'connections/drivers'), ('connections/manager.py', 'connections'), ('connections/mcp_presets.py', 'connections'), ('connections/oauth.py', 'connections'), ('connections/oauth_scopes.py', 'connections'), ('connections/registry.py', 'connections')],
    hiddenimports=['aiosqlite', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.lifespan', 'uvicorn.lifespan.on', 'connections', 'connections.base', 'connections.manager', 'connections.registry', 'connections.drivers', 'connections.drivers.google_calendar', 'connections.drivers.template_connector', 'connections.drivers.gmail', 'connections.drivers.mcp_client', 'connections.oauth', 'connections.oauth_scopes', 'connections.mcp_presets', 'policy.auto_approval', 'tools.mcp', 'tools.mcp.tool', 'tools.browser_auto', 'tools.browser_auto.tool'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
