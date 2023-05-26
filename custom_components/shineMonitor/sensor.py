import datetime
import hashlib
import requests
import time
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

DOMAIN = "shinemonitor"
BASE_URL = "http://web.shinemonitor.com/public/?sign="
PLANT_INFO = "&par=ENERGY_TODAY,ENERGY_MONTH,ENERGY_YEAR,ENERGY_TOTAL,ENERGY_PROCEEDS,ENERGY_CO2,CURRENT_TEMP,CURRENT_RADIANT,BATTERY_SOC,ENERGY_COAL,ENERGY_SO2"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required("company_id"): cv.string,
        vol.Required("plant_id"): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    company_id = config["company_id"]
    plant_id = config["plant_id"]
    api = API(username, password, company_id, plant_id)

    add_entities([ShineMonitorSensor(api)], True)


class API:
    def __init__(self, username, password, company_id, plant_id):
        self.username = username
        self.password = password
        self.salt = ""
        self.company_id = company_id
        self.plant_id = plant_id
        self.token = ""
        self.secret = ""
        self._login()

    def _get_salt(self):
        self.salt = str(round(time.time() * 1000))

    def _generate_password_hash(self):
        password_hash = hashlib.sha1(self.password.encode("utf-8")).hexdigest()
        return password_hash

    def _generate_sign(self):
        self._get_salt()
        sign_string = (
            self.salt
            + self._generate_password_hash()
            + "&action=auth&usr="
            + self.username
            + "&company-key="
            + self.company_id
        )
        return hashlib.sha1(sign_string.encode("utf-8")).hexdigest()

    def _login(self):
        self._get_salt()
        sign = self._generate_sign()

        url = (
            BASE_URL
            + sign
            + "&salt="
            + self.salt
            + "&action=auth&usr="
            + self.username
            + "&company-key="
            + self.company_id
        )
        data = requests.get(url).json()
        self.token = str(data["dat"]["token"])
        self.secret = str(data["dat"]["secret"])

    def get_action_values(self, query):
        self._login()
        action = (
            "&action="
            + query
            + "&plantid="
            + self.plant_id
            + "&date="
            + (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            + "&i18n=pt_BR&lang=pt_BR"
        )

        if query == Actions.PLANT_CURRENT_DATA.value:
            action += PLANT_INFO

        sign = hashlib.sha1(
            (self.salt + self.secret + self.token + action).encode("utf-8")
        ).hexdigest()

        url = (
            BASE_URL
            + sign
            + "&salt="
            + self.salt
            + "&token="
            + self.token
            + action
        )

        return requests.get(url).json()

    def get_power_day_per_time(self):
        data = self.get_action_values(Actions.POWER_DAY_PER_TIME.value)
        return data["value"]

    def get_power_month_per_day(self):
        data = self.get_action_values(Actions.POWER_MONTH_PER_DAY.value)
        return data["value"]

    def get_power_year_per_month(self):
        data = self.get_action_values(Actions.POWER_YEAR_PER_MONTH.value)
        return data["value"]

    def get_power_per_year(self):
        data = self.get_action_values(Actions.POWER_PER_YEAR.value)
        return data["value"]

    def get_device_status(self):
        data = self.get_action_values(Actions.DEVICE_STATUS.value)
        return data["value"]

    def get_plant_current_data(self):
        data = self.get_action_values(Actions.PLANT_CURRENT_DATA.value)
        return data["value"]


class ShineMonitorSensor(Entity):
    def __init__(self, api):
        self.api = api
        self._state = {}
        self._available_actions = {
            Actions.POWER_DAY_PER_TIME.value: self.api.get_power_day_per_time,
            Actions.POWER_MONTH_PER_DAY.value: self.api.get_power_month_per_day,
            Actions.POWER_YEAR_PER_MONTH.value: self.api.get_power_year_per_month,
            Actions.POWER_PER_YEAR.value: self.api.get_power_per_year,
            Actions.DEVICE_STATUS.value: self.api.get_device_status,
            Actions.PLANT_CURRENT_DATA.value: self.api.get_plant_current_data,
        }

    @property
    def name(self):
        return "ShineMonitor Sensor"

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return "kWh"

    def update(self):
        for action, method in self._available_actions.items():
            self._state[action] = method()


class Actions:
    POWER_DAY_PER_TIME = "queryPlantActiveOuputPowerOneDay"
    POWER_MONTH_PER_DAY = "queryPlantEnergyMonthPerDay"
    POWER_YEAR_PER_MONTH = "queryPlantEnergyYearPerMonth"
    POWER_PER_YEAR = "queryPlantEnergyTotalPerYear"
    DEVICE_STATUS = "queryPlantDeviceStatus"
    PLANT_CURRENT_DATA = "queryPlantCurrentData"
