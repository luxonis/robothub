from typing import Dict, Any

import depthai
import robothub_core


def stats_report(device: depthai.Device) -> Dict[str, Any]:
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


def info_report(device: depthai.Device, state: robothub_core.DeviceState) -> Dict[str, Any]:
    """
    Returns a dictionary with information about the device.
    """
    info = {
        'mxid': device.getMxId(),
        'protocol': 'unknown',
        'platform': 'unknown',
        'product_name': 'unknown',
        'board_name': 'unknown',
        'board_rev': 'unknown',
        'bootloader_version': 'unknown',
        'state': state.value,
    }

    device_info = try_or_default(device.getDeviceInfo)
    calibration = try_or_default(device.readFactoryCalibration) or try_or_default(device.readCalibration2)
    eeprom_data = try_or_default(calibration.getEepromData)

    bootloader_version = device.getBootloaderVersion()  # can be None
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
    try:
        return func()
    except:
        return default
