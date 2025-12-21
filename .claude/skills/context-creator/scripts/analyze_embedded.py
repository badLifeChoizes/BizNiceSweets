#!/usr/bin/env python3
"""
Embedded/IoT Analyzer
Detects embedded systems patterns including ESP-IDF, FreeRTOS, Arduino,
Zephyr, bare metal C, and hardware abstraction layers.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional


DETECTED = "detected"
INFERRED = "inferred"


# ========== Framework Detection ==========

EMBEDDED_FRAMEWORKS = {
    'esp-idf': {
        'files': ['sdkconfig', 'sdkconfig.defaults', 'CMakeLists.txt'],
        'dirs': ['components', 'main', 'managed_components'],
        'patterns': [r'#include\s*[<"]esp_', r'#include\s*[<"]freertos/', r'ESP_LOG'],
        'config_files': ['sdkconfig', 'Kconfig'],
    },
    'arduino': {
        'files': [],
        'extensions': ['.ino'],
        'patterns': [r'void\s+setup\s*\(\s*\)', r'void\s+loop\s*\(\s*\)', r'#include\s*[<"]Arduino\.h[">]'],
    },
    'zephyr': {
        'files': ['prj.conf', 'CMakeLists.txt'],
        'dirs': ['boards', 'dts'],
        'patterns': [r'#include\s*[<"]zephyr/', r'CONFIG_', r'K_THREAD_DEFINE'],
        'config_files': ['prj.conf', 'Kconfig'],
    },
    'freertos': {
        'patterns': [
            r'#include\s*[<"]FreeRTOS\.h[">]',
            r'xTaskCreate', r'vTaskDelay', r'xQueueCreate',
            r'xSemaphoreCreate', r'xTimerCreate',
        ],
    },
    'stm32-hal': {
        'files': [],
        'patterns': [r'#include\s*[<"]stm32\w+\.h[">]', r'HAL_GPIO_', r'HAL_UART_', r'__HAL_'],
        'dirs': ['Drivers', 'Core'],
    },
    'nrf-sdk': {
        'patterns': [r'#include\s*[<"]nrf', r'NRF_LOG_', r'APP_ERROR_CHECK'],
        'dirs': ['pca10056', 'pca10040'],
    },
    'mbed': {
        'files': ['mbed_app.json', '.mbed'],
        'patterns': [r'#include\s*[<"]mbed\.h[">]', r'DigitalOut', r'DigitalIn', r'Serial'],
    },
    'platformio': {
        'files': ['platformio.ini'],
        'dirs': ['.pio'],
    },
    'bare-metal': {
        'patterns': [
            r'volatile\s+\w+\s*\*',  # Memory-mapped registers
            r'__attribute__\s*\(\s*\(\s*interrupt', r'__interrupt',
            r'#pragma\s+interrupt',
        ],
    },
}


# ========== FreeRTOS Pattern Detection ==========

def analyze_freertos_patterns(source: str, filepath: Path) -> Dict:
    """Detect FreeRTOS usage patterns."""
    patterns = {
        'tasks': [],
        'queues': [],
        'semaphores': [],
        'mutexes': [],
        'timers': [],
        'event_groups': [],
        'task_notifications': False,
        'stack_sizes': [],
        'priorities': [],
    }

    # Task creation
    for match in re.finditer(r'xTaskCreate\s*\([^,]+,\s*["\']([^"\']+)["\']', source):
        patterns['tasks'].append(match.group(1))

    for match in re.finditer(r'xTaskCreateStatic\s*\([^,]+,\s*["\']([^"\']+)["\']', source):
        patterns['tasks'].append(match.group(1))

    # Stack sizes
    for match in re.finditer(r'(?:configMINIMAL_STACK_SIZE|STACK_SIZE)\s*\*?\s*(\d+)', source):
        patterns['stack_sizes'].append(int(match.group(1)))

    # Task priorities
    for match in re.finditer(r'tskIDLE_PRIORITY\s*\+\s*(\d+)', source):
        patterns['priorities'].append(int(match.group(1)))

    # Queues
    if re.search(r'xQueueCreate|xQueueCreateStatic', source):
        patterns['queues'].append(str(filepath))

    # Semaphores
    if re.search(r'xSemaphoreCreate(?:Binary|Counting|Mutex)|xSemaphoreCreateStatic', source):
        patterns['semaphores'].append(str(filepath))

    # Mutexes
    if re.search(r'xSemaphoreCreateMutex|xSemaphoreCreateRecursiveMutex', source):
        patterns['mutexes'].append(str(filepath))

    # Timers
    if re.search(r'xTimerCreate|xTimerCreateStatic', source):
        patterns['timers'].append(str(filepath))

    # Event groups
    if re.search(r'xEventGroupCreate|xEventGroupCreateStatic', source):
        patterns['event_groups'].append(str(filepath))

    # Task notifications
    if re.search(r'xTaskNotify|ulTaskNotifyTake|xTaskNotifyWait', source):
        patterns['task_notifications'] = True

    return patterns


# ========== ESP-IDF Pattern Detection ==========

def analyze_espidf_patterns(source: str, filepath: Path) -> Dict:
    """Detect ESP-IDF specific patterns."""
    patterns = {
        'components': [],
        'nvs_usage': False,
        'wifi': False,
        'bluetooth': False,
        'ble': False,
        'esp_now': False,
        'http_server': False,
        'mqtt': False,
        'ota': False,
        'spiffs': False,
        'fatfs': False,
        'gpio_usage': [],
        'peripherals': [],
        'logging_level': None,
        'partition_usage': False,
    }

    # WiFi
    if re.search(r'esp_wifi_|wifi_init|WIFI_MODE_', source):
        patterns['wifi'] = True

    # Bluetooth Classic
    if re.search(r'esp_bt_|esp_bluedroid_', source):
        patterns['bluetooth'] = True

    # BLE
    if re.search(r'esp_ble_|BLE_|ble_gap_|ble_gatt_', source):
        patterns['ble'] = True

    # ESP-NOW
    if re.search(r'esp_now_', source):
        patterns['esp_now'] = True

    # NVS
    if re.search(r'nvs_open|nvs_get_|nvs_set_|NVS_', source):
        patterns['nvs_usage'] = True

    # HTTP Server
    if re.search(r'httpd_start|httpd_register_', source):
        patterns['http_server'] = True

    # MQTT
    if re.search(r'esp_mqtt_|mqtt_client_', source):
        patterns['mqtt'] = True

    # OTA
    if re.search(r'esp_ota_|esp_https_ota', source):
        patterns['ota'] = True

    # File systems
    if re.search(r'esp_spiffs_|spiffs_', source):
        patterns['spiffs'] = True
    if re.search(r'esp_vfs_fat_|fatfs_', source):
        patterns['fatfs'] = True

    # GPIO
    for match in re.finditer(r'GPIO_NUM_(\d+)', source):
        patterns['gpio_usage'].append(int(match.group(1)))

    # Peripherals
    peripheral_patterns = {
        'uart': r'uart_driver_install|uart_config_t',
        'spi': r'spi_bus_initialize|spi_device_',
        'i2c': r'i2c_driver_install|i2c_master_',
        'adc': r'adc1_config_|adc2_config_|adc_oneshot_',
        'dac': r'dac_output_',
        'pwm': r'ledc_|mcpwm_',
        'timer': r'timer_init|gptimer_',
        'rtc': r'rtc_gpio_|esp_sleep_',
    }

    for peripheral, pattern in peripheral_patterns.items():
        if re.search(pattern, source):
            patterns['peripherals'].append(peripheral)

    # Partition table
    if re.search(r'esp_partition_|partition_table', source):
        patterns['partition_usage'] = True

    return patterns


# ========== Memory Pattern Detection ==========

def analyze_memory_patterns(source: str, filepath: Path) -> Dict:
    """Detect memory usage patterns in embedded code."""
    patterns = {
        'heap_usage': [],
        'stack_usage': [],
        'dma_buffers': False,
        'memory_pools': False,
        'static_allocation': 0,
        'dynamic_allocation': 0,
        'iram_usage': False,
        'dram_usage': False,
        'psram_usage': False,
    }

    # Dynamic allocation
    patterns['dynamic_allocation'] = len(re.findall(r'\bmalloc\s*\(|\bcalloc\s*\(|\brealloc\s*\(', source))

    # Static allocation (rough estimate)
    patterns['static_allocation'] = len(re.findall(r'static\s+\w+\s+\w+\s*(?:\[|=)', source))

    # ESP-IDF heap
    if re.search(r'heap_caps_malloc|heap_caps_get_free_size|esp_get_free_heap_size', source):
        patterns['heap_usage'].append(str(filepath))

    # DMA buffers
    if re.search(r'DMA_ATTR|__attribute__\s*\(\s*\(\s*aligned', source):
        patterns['dma_buffers'] = True

    # IRAM (instruction RAM)
    if re.search(r'IRAM_ATTR|__attribute__\s*\(\s*\(\s*section\s*\(\s*["\']\.iram', source):
        patterns['iram_usage'] = True

    # DRAM
    if re.search(r'DRAM_ATTR|__attribute__\s*\(\s*\(\s*section\s*\(\s*["\']\.dram', source):
        patterns['dram_usage'] = True

    # PSRAM (external RAM)
    if re.search(r'MALLOC_CAP_SPIRAM|esp_spiram_|CONFIG_SPIRAM', source):
        patterns['psram_usage'] = True

    return patterns


# ========== HAL/Driver Detection ==========

def analyze_hal_patterns(source: str, filepath: Path) -> Dict:
    """Detect hardware abstraction layer patterns."""
    patterns = {
        'gpio_abstraction': False,
        'uart_abstraction': False,
        'spi_abstraction': False,
        'i2c_abstraction': False,
        'timer_abstraction': False,
        'interrupt_handlers': [],
        'register_access': 0,
        'bit_manipulation': 0,
    }

    # Interrupt handlers
    isr_patterns = [
        r'void\s+\w+_IRQHandler\s*\(',  # ARM CMSIS style
        r'ISR\s*\(\s*\w+\s*\)',  # Arduino style
        r'__interrupt\s+void',  # TI style
        r'IRAM_ATTR\s+void\s+\w+_isr',  # ESP-IDF style
    ]
    for pattern in isr_patterns:
        for match in re.finditer(pattern, source):
            patterns['interrupt_handlers'].append(match.group(0)[:50])

    # Register access (memory-mapped I/O)
    patterns['register_access'] = len(re.findall(r'\*\s*\(\s*volatile\s+\w+\s*\*\s*\)', source))

    # Bit manipulation
    patterns['bit_manipulation'] = len(re.findall(r'(?:<<|>>|\||&)\s*(?:0x[\da-fA-F]+|\d+)', source))

    # HAL function patterns
    if re.search(r'(?:gpio|GPIO)_(?:init|config|set|get|read|write)', source, re.IGNORECASE):
        patterns['gpio_abstraction'] = True
    if re.search(r'(?:uart|UART)_(?:init|config|read|write|send|receive)', source, re.IGNORECASE):
        patterns['uart_abstraction'] = True
    if re.search(r'(?:spi|SPI)_(?:init|config|transfer|read|write)', source, re.IGNORECASE):
        patterns['spi_abstraction'] = True
    if re.search(r'(?:i2c|I2C)_(?:init|config|read|write|master|slave)', source, re.IGNORECASE):
        patterns['i2c_abstraction'] = True

    return patterns


# ========== Build System Detection ==========

def analyze_build_system(project_path: Path) -> Dict:
    """Detect embedded build system and configuration."""
    build_info = {
        'build_system': None,
        'config_files': [],
        'target_chip': None,
        'flash_size': None,
        'ram_size': None,
    }

    # CMake (ESP-IDF, Zephyr)
    if (project_path / 'CMakeLists.txt').exists():
        build_info['build_system'] = 'cmake'
        build_info['config_files'].append('CMakeLists.txt')

    # PlatformIO
    if (project_path / 'platformio.ini').exists():
        build_info['build_system'] = 'platformio'
        build_info['config_files'].append('platformio.ini')
        try:
            content = (project_path / 'platformio.ini').read_text()
            board_match = re.search(r'board\s*=\s*(\S+)', content)
            if board_match:
                build_info['target_chip'] = board_match.group(1)
        except:
            pass

    # ESP-IDF sdkconfig
    if (project_path / 'sdkconfig').exists():
        build_info['config_files'].append('sdkconfig')
        try:
            content = (project_path / 'sdkconfig').read_text()
            # Extract chip target
            target_match = re.search(r'CONFIG_IDF_TARGET="(\w+)"', content)
            if target_match:
                build_info['target_chip'] = target_match.group(1)
            # Flash size
            flash_match = re.search(r'CONFIG_ESPTOOLPY_FLASHSIZE_(\d+)MB=y', content)
            if flash_match:
                build_info['flash_size'] = f"{flash_match.group(1)}MB"
        except:
            pass

    # Makefile
    if (project_path / 'Makefile').exists():
        if not build_info['build_system']:
            build_info['build_system'] = 'make'
        build_info['config_files'].append('Makefile')

    # Arduino
    for ino in project_path.glob('*.ino'):
        build_info['build_system'] = 'arduino'
        build_info['config_files'].append(ino.name)
        break

    return build_info


# ========== Main Analysis ==========

def analyze_embedded(project_path: str) -> Dict:
    """Analyze project for embedded/IoT patterns."""
    root = Path(project_path).resolve()

    result = {
        'root': str(root),
        'is_embedded_project': False,
        'frameworks_detected': [],
        'build_system': None,
        'rtos': {
            'detected': False,
            'type': None,
            'tasks': [],
            'ipc_mechanisms': [],
        },
        'hardware': {
            'target_chip': None,
            'peripherals': [],
            'gpio_pins': [],
            'communication': [],
        },
        'memory': {
            'heap_monitoring': False,
            'static_heavy': False,
            'uses_psram': False,
            'uses_dma': False,
        },
        'connectivity': {
            'wifi': False,
            'bluetooth': False,
            'ble': False,
            'mqtt': False,
            'http': False,
        },
        'summary': {},
    }

    skip_dirs = {'node_modules', '.git', 'build', '.pio', 'managed_components'}

    # Build system detection
    build_info = analyze_build_system(root)
    result['build_system'] = build_info

    # Framework detection from files
    for framework, indicators in EMBEDDED_FRAMEWORKS.items():
        # Check for indicator files
        if 'files' in indicators:
            for fname in indicators['files']:
                if (root / fname).exists():
                    if framework not in result['frameworks_detected']:
                        result['frameworks_detected'].append(framework)
                    result['is_embedded_project'] = True

        # Check for indicator directories
        if 'dirs' in indicators:
            for dname in indicators['dirs']:
                if (root / dname).is_dir():
                    if framework not in result['frameworks_detected']:
                        result['frameworks_detected'].append(framework)
                    result['is_embedded_project'] = True

        # Check for extensions
        if 'extensions' in indicators:
            for ext in indicators['extensions']:
                if list(root.glob(f'**/*{ext}')):
                    if framework not in result['frameworks_detected']:
                        result['frameworks_detected'].append(framework)
                    result['is_embedded_project'] = True

    # Scan source files
    all_tasks = []
    all_peripherals = set()
    all_gpio = set()

    for filepath in root.rglob('*'):
        if any(skip in filepath.parts for skip in skip_dirs):
            continue
        if not filepath.is_file():
            continue

        suffix = filepath.suffix.lower()
        if suffix not in ('.c', '.h', '.cpp', '.hpp', '.ino'):
            continue

        try:
            source = filepath.read_text(encoding='utf-8', errors='replace')
        except:
            continue

        # Framework detection from patterns
        for framework, indicators in EMBEDDED_FRAMEWORKS.items():
            if 'patterns' in indicators:
                for pattern in indicators['patterns']:
                    if re.search(pattern, source):
                        if framework not in result['frameworks_detected']:
                            result['frameworks_detected'].append(framework)
                        result['is_embedded_project'] = True
                        break

        # FreeRTOS analysis
        if re.search(r'FreeRTOS|freertos', source, re.IGNORECASE):
            result['rtos']['detected'] = True
            result['rtos']['type'] = 'freertos'
            freertos_patterns = analyze_freertos_patterns(source, filepath)
            all_tasks.extend(freertos_patterns['tasks'])
            if freertos_patterns['queues']:
                result['rtos']['ipc_mechanisms'].append('queues')
            if freertos_patterns['semaphores']:
                result['rtos']['ipc_mechanisms'].append('semaphores')
            if freertos_patterns['mutexes']:
                result['rtos']['ipc_mechanisms'].append('mutexes')
            if freertos_patterns['event_groups']:
                result['rtos']['ipc_mechanisms'].append('event_groups')

        # ESP-IDF analysis
        if 'esp-idf' in result['frameworks_detected']:
            espidf_patterns = analyze_espidf_patterns(source, filepath)
            all_peripherals.update(espidf_patterns['peripherals'])
            all_gpio.update(espidf_patterns['gpio_usage'])

            if espidf_patterns['wifi']:
                result['connectivity']['wifi'] = True
            if espidf_patterns['bluetooth']:
                result['connectivity']['bluetooth'] = True
            if espidf_patterns['ble']:
                result['connectivity']['ble'] = True
            if espidf_patterns['mqtt']:
                result['connectivity']['mqtt'] = True
            if espidf_patterns['http_server']:
                result['connectivity']['http'] = True

        # Memory analysis
        mem_patterns = analyze_memory_patterns(source, filepath)
        if mem_patterns['heap_usage']:
            result['memory']['heap_monitoring'] = True
        if mem_patterns['psram_usage']:
            result['memory']['uses_psram'] = True
        if mem_patterns['dma_buffers']:
            result['memory']['uses_dma'] = True

        # HAL analysis
        hal_patterns = analyze_hal_patterns(source, filepath)

    # Deduplicate and summarize
    result['rtos']['tasks'] = list(set(all_tasks))
    result['rtos']['ipc_mechanisms'] = list(set(result['rtos']['ipc_mechanisms']))
    result['hardware']['peripherals'] = list(all_peripherals)
    result['hardware']['gpio_pins'] = sorted(all_gpio)
    result['hardware']['target_chip'] = build_info.get('target_chip')

    # Communication protocols
    if result['connectivity']['wifi'] or result['connectivity']['bluetooth']:
        result['hardware']['communication'].append('wireless')
    if 'uart' in all_peripherals:
        result['hardware']['communication'].append('uart')
    if 'spi' in all_peripherals:
        result['hardware']['communication'].append('spi')
    if 'i2c' in all_peripherals:
        result['hardware']['communication'].append('i2c')

    # Summary
    result['summary'] = {
        'is_embedded': result['is_embedded_project'],
        'frameworks': result['frameworks_detected'],
        'has_rtos': result['rtos']['detected'],
        'task_count': len(result['rtos']['tasks']),
        'peripheral_count': len(result['hardware']['peripherals']),
        'has_wireless': result['connectivity']['wifi'] or result['connectivity']['bluetooth'] or result['connectivity']['ble'],
    }

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_embedded.py <project_path> [--output file.json]", file=sys.stderr)
        sys.exit(1)

    project_path = sys.argv[1]
    output_file = None

    if '--output' in sys.argv:
        output_file = sys.argv[sys.argv.index('--output') + 1]

    result = analyze_embedded(project_path)

    # Print summary
    print(f"🔌 Embedded Analysis for {Path(project_path).name}")

    if not result['is_embedded_project']:
        print("   ℹ️  No embedded/IoT patterns detected")
    else:
        print(f"   Frameworks: {', '.join(result['frameworks_detected']) or 'None detected'}")

        if result['build_system'].get('build_system'):
            print(f"   Build system: {result['build_system']['build_system']}")

        if result['build_system'].get('target_chip'):
            print(f"   Target chip: {result['build_system']['target_chip']}")

        if result['rtos']['detected']:
            print(f"   RTOS: {result['rtos']['type']} ({len(result['rtos']['tasks'])} tasks)")
            if result['rtos']['ipc_mechanisms']:
                print(f"   IPC: {', '.join(result['rtos']['ipc_mechanisms'])}")

        if result['hardware']['peripherals']:
            print(f"   Peripherals: {', '.join(result['hardware']['peripherals'])}")

        if result['connectivity']['wifi'] or result['connectivity']['ble']:
            conn = []
            if result['connectivity']['wifi']:
                conn.append('WiFi')
            if result['connectivity']['ble']:
                conn.append('BLE')
            if result['connectivity']['mqtt']:
                conn.append('MQTT')
            print(f"   Connectivity: {', '.join(conn)}")

    if output_file:
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\n💾 Saved to {output_file}")
    else:
        print()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
