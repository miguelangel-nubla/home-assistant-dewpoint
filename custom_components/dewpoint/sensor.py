"""
Calculate Dew Point based on temperature and humidity sensors

For more details about this platform, please refer to the documentation
https://github.com/miguelangel-nubla/home-assistant-dewpoint
"""

import logging
import asyncio

import voluptuous as vol


from homeassistant.core import callback
from homeassistant.const import (
    TEMP_CELSIUS, ATTR_FRIENDLY_NAME, ATTR_ENTITY_ID, CONF_SENSORS,
    EVENT_HOMEASSISTANT_START, ATTR_UNIT_OF_MEASUREMENT, ATTR_TEMPERATURE)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change
import homeassistant.helpers.config_validation as cv

from homeassistant.components.sensor import PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)

CONF_REL_HUM = 'rel_hum'

SENSOR_SCHEMA = vol.Schema({
    vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
    vol.Required(ATTR_TEMPERATURE): cv.entity_id,
    vol.Required(CONF_REL_HUM): cv.entity_id
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(SENSOR_SCHEMA),
})


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Setup the sensor platform."""

    for device, device_config in config[CONF_SENSORS].items():
        friendly_name = device_config.get(ATTR_FRIENDLY_NAME, device)
        entity_dry_temp = device_config.get(ATTR_TEMPERATURE)
        entity_rel_hum = device_config.get(CONF_REL_HUM)

        async_add_entities([DewPointSensor(hass, device, friendly_name, entity_dry_temp, entity_rel_hum)])


class DewPointSensor(Entity):

    def __init__(self, hass, unique_id, name, entity_dry_temp, entity_rel_hum):
        """Initialize the sensor."""
        self.hass = hass
        self._state = None
        self._unique_id = unique_id
        self._name = name

        self._entity_dry_temp = entity_dry_temp
        self._entity_rel_hum = entity_rel_hum

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def sensor_state_listener(entity, old_state, new_state):
            """Handle device state changes."""
            self.async_schedule_update_ha_state(True)

        @callback
        def sensor_startup(event):
            """Update template on startup."""
            async_track_state_change(
                self.hass, [self._entity_dry_temp, self._entity_rel_hum], sensor_state_listener)

            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, sensor_startup)

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @callback
    def get_dry_temp(self, entity):
        state = self.hass.states.get(entity)

        if state.state is None or state.state == 'unknown':
            _LOGGER.error('Unable to read temperature from unavailable sensor: %s', self._entity_dry_temp)
            return

        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        try:
            return self.hass.config.units.temperature(
                float(state.state), unit)
        except ValueError as ex:
            _LOGGER.error('Unable to read temperature from sensor: %s', ex)

    @callback
    def get_rel_hum(self, entity):
        state = self.hass.states.get(entity)

        if state.state is None or state.state == 'unknown':
            _LOGGER.error('Unable to read relative humidity from unavailable sensor: %s', self._entity_dry_temp)
            return

        try:
            return float(state.state)/100
        except ValueError as ex:
            _LOGGER.error('Unable to read relative humidity from sensor: %s', ex)

    async def async_update(self):
        """Fetch new state data for the sensor."""

        dry_temp = self.get_dry_temp(self._entity_dry_temp)
        rel_hum = self.get_rel_hum(self._entity_rel_hum)
        if dry_temp and rel_hum:
            import psychrolib
            psychrolib.SetUnitSystem(psychrolib.SI)
            TDewPoint = psychrolib.GetTDewPointFromRelHum(dry_temp, rel_hum)
            self._state = round(TDewPoint, 2)