import logging
from typing import Any, Dict

import depthai
try:
    import robothub_core
except ImportError:
    import robothub.robothub_core_wrapper as robothub_core

__all__ = ['setup_logger', 'get_device_performance_metrics', 'get_device_details', 'try_or_default']


def setup_logger(name: str, level: int = logging.INFO):
    """
    Initializes a logger with the given name and level.

    :param name: Logger name.
    :param level: Either a string or an integer. If a string, it must be one of the following: 'DEBUG', 'INFO',
    'WARNING', 'ERROR', 'CRITICAL'. If an integer, it must be one of the following: log.DEBUG, log.INFO, log.WARNING,
    log.ERROR, log.CRITICAL.
    """
    if isinstance(level, str):
        level = level.upper()
    logger = logging.getLogger(name)
    logger.setLevel(level)

    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    format_str = '%(levelname)s | %(name)s | %(message)s' if level == logging.DEBUG else '%(levelname)s | %(message)s'
    formatter = logging.Formatter(format_str)
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def get_device_performance_metrics(device: depthai.Device) -> Dict[str, Any]:
    """
    Returns a dictionary with statistics about the device.
    """
    stats = {'mxid': device.getMxId()}

    css_cpu_usage = device.getLeonCssCpuUsage().average
    mss_cpu_usage = device.getLeonMssCpuUsage().average
    cmx_mem_usage = device.getCmxMemoryUsage()
    ddr_mem_usage = device.getDdrMemoryUsage()
    chip_temp = device.getChipTemperature()

    stats['css_usage'] = int(100 * css_cpu_usage)
    stats['mss_usage'] = int(100 * mss_cpu_usage)
    stats['ddr_mem_free'] = int(ddr_mem_usage.total - ddr_mem_usage.used)
    stats['ddr_mem_total'] = int(ddr_mem_usage.total)
    stats['cmx_mem_free'] = int(cmx_mem_usage.total - cmx_mem_usage.used)
    stats['cmx_mem_total'] = int(cmx_mem_usage.total)
    stats['css_temp'] = int(100 * chip_temp.css)
    stats['mss_temp'] = int(100 * chip_temp.mss)
    stats['upa_temp'] = int(100 * chip_temp.upa)
    stats['dss_temp'] = int(100 * chip_temp.dss)
    stats['temp'] = int(100 * chip_temp.average)

    return stats


def get_device_details(device: depthai.Device, state: robothub_core.DeviceState) -> Dict[str, Any]:
    """
    Returns a dictionary with information about the device.
    """
    info = {
        'mxid': 'unknown',
        'state': state.value,
        'protocol': 'unknown',
        'platform': 'unknown',
        'product_name': 'unknown',
        'board_name': 'unknown',
        'board_rev': 'unknown',
        'bootloader_version': 'unknown'
    }

    if device is None:
        return info

    mxid = try_or_default(device.getMxId)
    bootloader_version = device.getBootloaderVersion()  # can be None
    calibration = try_or_default(device.readFactoryCalibration) or try_or_default(device.readCalibration2)
    eeprom_data = try_or_default(calibration.getEepromData)
    device_info = try_or_default(device.getDeviceInfo)

    if mxid:
        info['mxid'] = mxid

    if bootloader_version:
        info['bootloader_version'] = bootloader_version.toStringSemver()

    if eeprom_data:
        info['product_name'] = eeprom_data.productName
        info['board_name'] = eeprom_data.boardName
        info['board_rev'] = eeprom_data.boardRev

    if device_info:
        info['protocol'] = device_info.protocol.name
        info['platform'] = device_info.platform.name

    return info


def try_or_default(func, default=None):
    """
    Tries to call the given function and returns its result. If an exception is raised, returns the default value.
    """
    try:
        return func()
    except Exception:
        return default
