import { useState } from 'react';
import { ConfigPanel } from './ConfigPanel';
import useWizardStore from '../../stores/wizardStore';
import { useAllTemplates, useBoard, useToolboard } from '../../hooks';
import { usePortRegistry } from '../../hooks/usePortRegistry';
import { PortSelector } from '../ui/PortSelector';
import type { SimplePort, MotorPort, ProbePort } from '../ui/PortSelector';
import { Crosshair, Usb, Radio, CircuitBoard, Cpu, Thermometer, Activity, Info, ChevronDown } from 'lucide-react';

// Type guard for ProbePort
function isProbePort(port: MotorPort | SimplePort | ProbePort): port is ProbePort {
  return 'signal_pin' in port;
}

// Type guard for SimplePort
function isSimplePort(port: MotorPort | SimplePort | ProbePort): port is SimplePort {
  return 'pin' in port && !('step_pin' in port);
}

// Probe connection types
type ProbeConnection = 'usb' | 'can' | 'i2c' | 'gpio' | 'manual';

// Probes that use USB/CAN and provide z_virtual_endstop
const USB_CAN_PROBES = ['beacon', 'cartographer', 'btt-eddy'];

// Probes that have built-in accelerometer
const PROBES_WITH_ACCEL = ['beacon', 'cartographer'];

// Probes that have coil temperature sensor
const PROBES_WITH_TEMP = ['beacon', 'cartographer', 'btt-eddy'];

export function ProbePanel() {
  const setActivePanel = useWizardStore((state) => state.setActivePanel);
  const setField = useWizardStore((state) => state.setField);
  const state = useWizardStore((state) => state.state);

  const { data: templates } = useAllTemplates();

  // Get board data
  const selectedBoard = state['mcu.main.board_type'];
  const { data: boardData } = useBoard(selectedBoard);
  const toolboardEnabled = state['mcu.toolboard.enabled'] ?? false;
  const selectedToolboard = state['mcu.toolboard.board_type'];
  const { data: toolboardData } = useToolboard(selectedToolboard);
  const portRegistry = usePortRegistry(state, boardData, toolboardData);

  const [showAdvanced, setShowAdvanced] = useState(false);

  const getValue = (key: string, defaultVal?: any) => {
    const val = state[`probe.${key}`];
    return val !== undefined ? val : defaultVal;
  };
  const setValue = (key: string, value: any) => setField(`probe.${key}`, value);

  const probeType = getValue('probe_type');
  const connection = getValue('connection') as ProbeConnection;

  // Determine if this is a USB/CAN probe
  const isUsbCanProbe = USB_CAN_PROBES.includes(probeType);
  const hasAccelerometer = PROBES_WITH_ACCEL.includes(probeType);
  const hasTemperatureSensor = PROBES_WITH_TEMP.includes(probeType);

  // Handle probe type change
  const handleProbeTypeChange = (newType: string) => {
    setValue('probe_type', newType || undefined);

    // Auto-set connection type based on probe
    if (USB_CAN_PROBES.includes(newType)) {
      setValue('connection', 'usb');
      // Clear GPIO-based settings
      setValue('port', undefined);
      setValue('pin', undefined);
      setValue('endstop_port', undefined);
    } else if (newType === 'manual') {
      setValue('connection', 'manual');
      setValue('serial', undefined);
      setValue('canbus_uuid', undefined);
    } else if (newType) {
      setValue('connection', 'gpio');
      setValue('serial', undefined);
      setValue('canbus_uuid', undefined);
    }
  };

  // Handle probe port selection (for GPIO probes)
  const handleProbePortChange = (portId: string, portData?: MotorPort | SimplePort | ProbePort) => {
    setValue('port', portId || undefined);
    if (portData) {
      const prefix = getValue('location') === 'toolboard' ? 'toolboard:' : '';
      if (isProbePort(portData)) {
        setValue('pin', `^${prefix}${portData.signal_pin}`);
        if (portData.servo_pin) {
          setValue('servo_pin', `${prefix}${portData.servo_pin}`);
        }
      } else if (isSimplePort(portData)) {
        setValue('pin', `^${prefix}${portData.pin}`);
      }
    } else {
      setValue('pin', undefined);
      setValue('servo_pin', undefined);
    }
  };

  // Handle endstop port selection (for manual Z endstop)
  const handleEndstopPortChange = (portId: string, portData?: MotorPort | SimplePort | ProbePort) => {
    setValue('endstop_port', portId || undefined);
    if (portData && isSimplePort(portData)) {
      const prefix = getValue('location') === 'toolboard' ? 'toolboard:' : '';
      setValue('pin', `^${prefix}${portData.pin}`);
    } else {
      setValue('pin', undefined);
    }
  };

  // Get active board data based on location
  const location = getValue('location', 'mainboard');
  const activeBoardData = location === 'toolboard' && toolboardData ? toolboardData : boardData;

  return (
    <ConfigPanel title="Probe / Z-Endstop" onClose={() => setActivePanel(null)}>
      <div className="space-y-6">
        {/* Info */}
        <div className="bg-violet-900/30 border border-violet-700 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <Crosshair className="text-violet-400 shrink-0 mt-0.5" size={20} />
            <div>
              <div className="text-sm font-medium text-violet-300">Bed Probe / Z Endstop</div>
              <p className="text-xs text-violet-200/70 mt-1">
                Configure your bed leveling probe for mesh bed leveling and Z homing.
                USB probes like Beacon/Cartographer provide their own virtual endstop.
              </p>
            </div>
          </div>
        </div>

        {/* Probe Type */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Probe Type
          </label>
          <select
            value={probeType || ''}
            onChange={(e) => handleProbeTypeChange(e.target.value)}
            className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
          >
            <option value="">Select a probe...</option>
            <optgroup label="Eddy Current (USB/CAN)">
              <option value="beacon">Beacon (USB)</option>
              <option value="cartographer">Cartographer (USB/CAN)</option>
              <option value="btt-eddy">BTT Eddy USB</option>
            </optgroup>
            <optgroup label="Eddy Current (I2C - Toolboard)">
              <option value="btt-eddy-coil">BTT Eddy Coil (I2C)</option>
            </optgroup>
            <optgroup label="Traditional Probes">
              {templates?.probes
                .filter((p) => !USB_CAN_PROBES.includes(p.id) && p.id !== 'btt-eddy')
                .map((probe) => (
                  <option key={probe.id} value={probe.id}>
                    {probe.name}
                  </option>
                ))}
            </optgroup>
            <option value="manual">Manual Z Endstop (Switch)</option>
          </select>
        </div>

        {/* USB/CAN Probe Configuration */}
        {isUsbCanProbe && (
          <div className="space-y-4">
            {/* Connection Type */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Connection Type
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => setValue('connection', 'usb')}
                  className={`flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-colors ${
                    connection === 'usb'
                      ? 'bg-violet-600 text-white'
                      : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                  }`}
                >
                  <Usb size={16} />
                  USB
                </button>
                {probeType === 'cartographer' && (
                  <button
                    onClick={() => setValue('connection', 'can')}
                    className={`flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-colors ${
                      connection === 'can'
                        ? 'bg-violet-600 text-white'
                        : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                    }`}
                  >
                    <Radio size={16} />
                    CAN
                  </button>
                )}
              </div>
            </div>

            {/* Serial ID (USB) */}
            {connection === 'usb' && (
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Serial ID
                </label>
                <input
                  type="text"
                  value={getValue('serial') || ''}
                  onChange={(e) => setValue('serial', e.target.value || undefined)}
                  placeholder={
                    probeType === 'beacon'
                      ? '/dev/serial/by-id/usb-Beacon_Beacon_RevH_XXXXXXXX-if00'
                      : probeType === 'cartographer'
                      ? '/dev/serial/by-id/usb-Cartographer_XXXXXXXX'
                      : '/dev/serial/by-id/usb-Klipper_rp2040_XXXXXXXX-if00'
                  }
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 font-mono text-sm"
                />
                <p className="text-xs text-slate-500 mt-1">
                  Find with: <code className="bg-slate-800 px-1 rounded">ls /dev/serial/by-id/</code>
                </p>
              </div>
            )}

            {/* CAN UUID */}
            {connection === 'can' && (
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  CAN Bus UUID
                </label>
                <input
                  type="text"
                  value={getValue('canbus_uuid') || ''}
                  onChange={(e) => setValue('canbus_uuid', e.target.value || undefined)}
                  placeholder="e.g., 1a2b3c4d5e6f"
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 font-mono text-sm"
                />
                <p className="text-xs text-slate-500 mt-1">
                  Find with: <code className="bg-slate-800 px-1 rounded">~/klippy-env/bin/python ~/klipper/scripts/canbus_query.py can0</code>
                </p>
              </div>
            )}

            {/* Z Endstop info */}
            <div className="bg-emerald-900/20 border border-emerald-700/50 rounded-lg p-3">
              <div className="flex items-start gap-2">
                <Info size={14} className="text-emerald-400 shrink-0 mt-0.5" />
                <div className="text-xs text-emerald-300">
                  <strong>Z Endstop:</strong> This probe provides <code className="bg-slate-800 px-1 rounded">probe:z_virtual_endstop</code>
                  <br />
                  <span className="text-emerald-200/70">
                    Set <code className="bg-slate-800 px-1 rounded">homing_retract_dist: 0</code> in stepper_z for eddy probes.
                  </span>
                </div>
              </div>
            </div>

            {/* Beacon-specific options */}
            {probeType === 'beacon' && (
              <div className="space-y-3 border-t border-slate-700 pt-4">
                <h4 className="text-sm font-medium text-slate-300">Beacon Options</h4>

                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">
                    Home Method
                  </label>
                  <select
                    value={getValue('home_method', 'contact')}
                    onChange={(e) => setValue('home_method', e.target.value)}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-cyan-500"
                  >
                    <option value="contact">Contact (Rev H+)</option>
                    <option value="proximity">Proximity</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">
                    Contact Max Hotend Temp (°C)
                  </label>
                  <input
                    type="number"
                    value={getValue('contact_max_hotend_temperature', 180)}
                    onChange={(e) => setValue('contact_max_hotend_temperature', parseInt(e.target.value) || undefined)}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-cyan-500"
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* BTT Eddy Coil (I2C) Configuration */}
        {probeType === 'btt-eddy-coil' && (
          <div className="space-y-4">
            <div className="bg-amber-900/20 border border-amber-700/50 rounded-lg p-3">
              <div className="flex items-start gap-2">
                <Info size={14} className="text-amber-400 shrink-0 mt-0.5" />
                <div className="text-xs text-amber-300">
                  <strong>BTT Eddy Coil</strong> connects via I2C to your toolboard.
                  <br />
                  <span className="text-amber-200/70">
                    Note: No temperature compensation - less reliable for Z homing in heated chambers.
                  </span>
                </div>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                I2C MCU (Toolboard)
              </label>
              <input
                type="text"
                value={getValue('i2c_mcu', 'toolboard')}
                onChange={(e) => setValue('i2c_mcu', e.target.value || undefined)}
                placeholder="e.g., toolboard, EBBCan"
                className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:border-cyan-500 font-mono text-sm"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                I2C Bus
              </label>
              <input
                type="text"
                value={getValue('i2c_bus', 'i2c3_PB3_PB4')}
                onChange={(e) => setValue('i2c_bus', e.target.value || undefined)}
                placeholder="e.g., i2c3_PB3_PB4"
                className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:border-cyan-500 font-mono text-sm"
              />
              <p className="text-xs text-slate-500 mt-1">
                Check your toolboard documentation for the correct I2C bus
              </p>
            </div>
          </div>
        )}

        {/* Traditional GPIO Probe Configuration */}
        {probeType && !isUsbCanProbe && probeType !== 'manual' && probeType !== 'btt-eddy-coil' && (
          <div className="space-y-4">
            {/* Location selector */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Probe Connected To
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => {
                    setValue('location', 'mainboard');
                    setValue('port', undefined);
                    setValue('pin', undefined);
                  }}
                  className={`flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-colors ${
                    location === 'mainboard'
                      ? 'bg-cyan-600 text-white'
                      : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                  }`}
                >
                  <Cpu size={16} />
                  Mainboard
                </button>
                {toolboardEnabled && toolboardData && (
                  <button
                    onClick={() => {
                      setValue('location', 'toolboard');
                      setValue('port', undefined);
                      setValue('pin', undefined);
                    }}
                    className={`flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-colors ${
                      location === 'toolboard'
                        ? 'bg-emerald-600 text-white'
                        : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                    }`}
                  >
                    <CircuitBoard size={16} />
                    Toolboard
                  </button>
                )}
              </div>
            </div>

            {/* Port Selection */}
            <PortSelector
              label="Probe Port"
              portType="probe"
              value={getValue('port') || ''}
              onChange={handleProbePortChange}
              boardData={activeBoardData}
              usedPorts={portRegistry.getUsedByType('probe')}
              placeholder={`Select probe port from ${location}...`}
              allowClear={true}
            />

            {/* Show configured pin */}
            {getValue('pin') && (
              <div className="bg-slate-800/50 rounded-lg p-2 border border-slate-700">
                <div className="text-xs text-slate-400">
                  Probe pin: <span className="font-mono text-emerald-400">{getValue('pin')}</span>
                </div>
                {getValue('servo_pin') && (
                  <div className="text-xs text-slate-400 mt-1">
                    Servo pin: <span className="font-mono text-emerald-400">{getValue('servo_pin')}</span>
                  </div>
                )}
              </div>
            )}

            {/* Z Endstop info for GPIO probes */}
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
              <div className="text-xs text-slate-400">
                <strong>Z Endstop:</strong> Use <code className="bg-slate-700 px-1 rounded">probe:z_virtual_endstop</code> in stepper_z
              </div>
            </div>
          </div>
        )}

        {/* Manual Z Endstop Configuration */}
        {probeType === 'manual' && (
          <div className="space-y-4">
            {/* Location selector */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Endstop Connected To
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => {
                    setValue('location', 'mainboard');
                    setValue('endstop_port', undefined);
                    setValue('pin', undefined);
                  }}
                  className={`flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-colors ${
                    location === 'mainboard'
                      ? 'bg-cyan-600 text-white'
                      : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                  }`}
                >
                  <Cpu size={16} />
                  Mainboard
                </button>
                {toolboardEnabled && toolboardData && (
                  <button
                    onClick={() => {
                      setValue('location', 'toolboard');
                      setValue('endstop_port', undefined);
                      setValue('pin', undefined);
                    }}
                    className={`flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-colors ${
                      location === 'toolboard'
                        ? 'bg-emerald-600 text-white'
                        : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                    }`}
                  >
                    <CircuitBoard size={16} />
                    Toolboard
                  </button>
                )}
              </div>
            </div>

            {/* Endstop Port Selection */}
            <PortSelector
              label="Endstop Port"
              portType="endstop"
              value={getValue('endstop_port') || ''}
              onChange={handleEndstopPortChange}
              boardData={activeBoardData}
              usedPorts={portRegistry.getUsedByType('endstop')}
              placeholder={`Select Z endstop port from ${location}...`}
              allowClear={true}
            />

            {/* Show configured pin */}
            {getValue('pin') && (
              <div className="bg-slate-800/50 rounded-lg p-2 border border-slate-700">
                <div className="text-xs text-slate-400">
                  Endstop pin: <span className="font-mono text-emerald-400">{getValue('pin')}</span>
                </div>
              </div>
            )}

            <div className="bg-amber-900/20 border border-amber-700/50 rounded-lg p-3">
              <div className="text-xs text-amber-300">
                <strong>Note:</strong> Manual Z endstop requires separate bed mesh probing.
                Consider adding a probe for automatic bed leveling.
              </div>
            </div>
          </div>
        )}

        {/* Probe Offsets (for all probe types except manual) */}
        {probeType && probeType !== 'manual' && (
          <div className="border-t border-slate-700 pt-4">
            <h3 className="text-sm font-medium text-slate-300 mb-3">Probe Offsets</h3>
            <p className="text-xs text-slate-500 mb-4">
              Distance from nozzle to probe trigger point
            </p>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">X Offset</label>
                <input
                  type="number"
                  step="0.1"
                  value={getValue('x_offset') ?? ''}
                  onChange={(e) => setValue('x_offset', e.target.value ? parseFloat(e.target.value) : undefined)}
                  placeholder="0"
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-2 py-1.5 text-white text-sm placeholder-slate-500 focus:border-cyan-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Y Offset</label>
                <input
                  type="number"
                  step="0.1"
                  value={getValue('y_offset') ?? ''}
                  onChange={(e) => setValue('y_offset', e.target.value ? parseFloat(e.target.value) : undefined)}
                  placeholder="0"
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-2 py-1.5 text-white text-sm placeholder-slate-500 focus:border-cyan-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Z Offset</label>
                <input
                  type="number"
                  step="0.01"
                  value={getValue('z_offset') ?? ''}
                  onChange={(e) => setValue('z_offset', e.target.value ? parseFloat(e.target.value) : undefined)}
                  placeholder="0"
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-2 py-1.5 text-white text-sm placeholder-slate-500 focus:border-cyan-500"
                />
              </div>
            </div>
          </div>
        )}

        {/* Accelerometer Configuration */}
        {(hasAccelerometer || toolboardEnabled) && (
          <div className="border-t border-slate-700 pt-4">
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center gap-2 text-sm font-medium text-slate-300 hover:text-white transition-colors"
            >
              <ChevronDown size={16} className={`transition-transform ${showAdvanced ? 'rotate-180' : ''}`} />
              Accelerometer & Temperature Sensor
            </button>

            {showAdvanced && (
              <div className="mt-4 space-y-4">
                {/* Accelerometer */}
                <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                  <div className="flex items-center gap-2 mb-3">
                    <Activity size={16} className="text-cyan-400" />
                    <h4 className="text-sm font-medium text-slate-300">Accelerometer (Input Shaper)</h4>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-2">
                      Accelerometer Location
                    </label>
                    <select
                      value={getValue('accel_location', hasAccelerometer ? 'probe' : 'none')}
                      onChange={(e) => setValue('accel_location', e.target.value || undefined)}
                      className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-cyan-500"
                    >
                      <option value="none">None / Not configured</option>
                      {hasAccelerometer && (
                        <option value="probe">On Probe ({probeType})</option>
                      )}
                      {toolboardEnabled && (
                        <option value="toolboard">On Toolboard</option>
                      )}
                      <option value="host">Direct to Host (SPI/USB)</option>
                      <option value="mainboard">On Mainboard</option>
                    </select>
                  </div>

                  {getValue('accel_location') === 'host' && (
                    <div className="mt-3">
                      <label className="block text-xs font-medium text-slate-400 mb-1">
                        Accelerometer Type
                      </label>
                      <select
                        value={getValue('accel_type', 'adxl345')}
                        onChange={(e) => setValue('accel_type', e.target.value)}
                        className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-cyan-500"
                      >
                        <option value="adxl345">ADXL345 (SPI)</option>
                        <option value="mpu9250">MPU-9250</option>
                        <option value="lis2dw">LIS2DW</option>
                      </select>
                    </div>
                  )}

                  {getValue('accel_location') === 'toolboard' && (
                    <p className="text-xs text-slate-500 mt-2">
                      Uses accelerometer on toolboard. Check your toolboard documentation for pin configuration.
                    </p>
                  )}
                </div>

                {/* Coil Temperature Sensor */}
                {hasTemperatureSensor && (
                  <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                    <div className="flex items-center gap-2 mb-3">
                      <Thermometer size={16} className="text-orange-400" />
                      <h4 className="text-sm font-medium text-slate-300">Probe Temperature Sensor</h4>
                    </div>

                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={getValue('enable_temp_sensor', true)}
                        onChange={(e) => setValue('enable_temp_sensor', e.target.checked)}
                        className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-cyan-500 focus:ring-cyan-500"
                      />
                      <span className="text-sm text-slate-300">
                        Enable coil temperature sensor
                      </span>
                    </label>
                    <p className="text-xs text-slate-500 mt-2">
                      Used for temperature drift compensation on eddy current probes.
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Homing Position (for probes that need it) */}
        {isUsbCanProbe && (
          <div className="border-t border-slate-700 pt-4">
            <h3 className="text-sm font-medium text-slate-300 mb-3">Safe Z Home Position</h3>
            <p className="text-xs text-slate-500 mb-4">
              XY position for Z homing (typically center of bed)
            </p>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Home X</label>
                <input
                  type="number"
                  step="1"
                  value={getValue('home_xy_position_x') ?? ''}
                  onChange={(e) => setValue('home_xy_position_x', e.target.value ? parseFloat(e.target.value) : undefined)}
                  placeholder="e.g., 150"
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-2 py-1.5 text-white text-sm placeholder-slate-500 focus:border-cyan-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Home Y</label>
                <input
                  type="number"
                  step="1"
                  value={getValue('home_xy_position_y') ?? ''}
                  onChange={(e) => setValue('home_xy_position_y', e.target.value ? parseFloat(e.target.value) : undefined)}
                  placeholder="e.g., 150"
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-2 py-1.5 text-white text-sm placeholder-slate-500 focus:border-cyan-500"
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </ConfigPanel>
  );
}
