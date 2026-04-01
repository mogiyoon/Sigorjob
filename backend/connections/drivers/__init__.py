from connections.drivers.google_calendar import GoogleCalendarConnectorDriver
from connections.drivers.template_connector import TemplateConnectorDriver


def list_connector_drivers():
    return [
        GoogleCalendarConnectorDriver(),
        TemplateConnectorDriver(),
    ]
