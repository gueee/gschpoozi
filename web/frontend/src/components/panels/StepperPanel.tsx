import { ConfigPanel } from './ConfigPanel';
import useWizardStore from '../../stores/wizardStore';
import { useBoard, useToolboard } from '../../hooks/useTemplates';
import { usePortRegistry } from '../../hooks/usePortRegistry';
import { PortSelector } from '../ui/PortSelector';
import { PinEditor } from '../ui/PinEditor';
import type { MotorPort, SimplePort, ProbePort } from '../ui/PortSelector';
import { Settings, Info, Cpu, CircuitBoard } from 'lucide-react';

interface StepperPanelProps {
  stepperName: string;
}

const DRIVER_TYPES = [
  { id: 'tmc2209', name: 'TMC2209', description: 'UART, StealthChop, great for most builds', sensorless: true, interface: 'uart' },
  { id: 'tmc2208', name: 'TMC2208', description: 'UART, StealthChop, quieter but less features', sensorless: false, interface: 'uart' },
  { id: 'tmc2226', name: 'TMC2226', description: 'UART, StealthChop, improved TMC2209', sensorless: true, interface: 'uart' },
  { id: 'tmc5160', name: 'TMC5160', description: 'SPI, high current capability, premium choice', sensorless: true, interface: 'spi' },
  { id: 'tmc2130', name: 'TMC2130', description: 'SPI, StealthChop, classic choice', sensorless: true, interface: 'spi' },
  { id: 'tmc2240', name: 'TMC2240', description: 'SPI/UART, newest generation', sensorless: true, interface: 'spi' },
  { id: 'a4988', name: 'A4988', description: 'Basic stepper driver, no UART/SPI', sensorless: false, interface: 'none' },
  { id: 'drv8825', name: 'DRV8825', description: 'Basic driver, higher microstepping', sensorless: false, interface: 'none' },
];

const MICROSTEP_OPTIONS = [16, 32, 64, 128, 256];

export function StepperPanel({ stepperName }: StepperPanelProps) {
  const setActivePanel = useWizardStore((state) => state.setActivePanel);
  const setField = useWizardStore((state) => state.setField);
  const state = useWizardStore((state) => state.state);

  // Get mainboard data for port selection
  const selectedBoard = state['mcu.main.board_type'];
  const { data: boardData } = useBoard(selectedBoard);

  // Get toolboard data
  const toolboardEnabled = state['mcu.toolboard.enabled'] ?? false;
  const selectedToolboard = state['mcu.toolboard.board_type'];
  const { data: toolboardData } = useToolboard(selectedToolboard);

  const portRegistry = usePortRegistry(state, boardData, toolboardData);

  const prefix = stepperName;
  const displayName = stepperName.replace('stepper_', '').toUpperCase();
  const isZAxis = stepperName.includes('z');

  const getValue = (key: string, defaultVal?: any) => {
    const val = state[`${prefix}.${key}`];
    // Return undefined if not set (not default values for optional fields)
    return val !== undefined ? val : defaultVal;
  };

  const setValue = (key: string, value: any) => setField(`${prefix}.${key}`, value);

  // Get currently selected motor port data
  const selectedMotorPort = getValue('motor_port');
  const motorPortData = boardData?.motor_ports?.[selectedMotorPort] as MotorPort | undefined;

  // Get all GPIO pins from board for advanced override
  const availablePins = boardData?.all_pins || [];

  // Current pin values from state
  const currentPins = {
    step_pin: getValue('step_pin'),
    dir_pin: getValue('dir_pin'),
    enable_pin: getValue('enable_pin'),
    uart_pin: getValue('uart_pin'),
    cs_pin: getValue('cs_pin'),
    diag_pin: getValue('diag_pin'),
  };

  // Handle motor port selection - auto-fill related pins
  const handleMotorPortChange = (portId: string, portData?: MotorPort | SimplePort | ProbePort) => {
    if (!portId) {
      // Clear port and all associated pins
      setValue('motor_port', undefined);
      setValue('step_pin', undefined);
      setValue('dir_pin', undefined);
      setValue('enable_pin', undefined);
      setValue('uart_pin', undefined);
      setValue('cs_pin', undefined);
      setValue('diag_pin', undefined);
      return;
    }

    setValue('motor_port', portId);

    if (portData && 'step_pin' in portData) {
      const motor = portData as MotorPort;
      setValue('step_pin', motor.step_pin);
      setValue('dir_pin', motor.dir_pin);
      // Enable is typically active-low in Klipper
      setValue('enable_pin', '!' + motor.enable_pin);
      if (motor.uart_pin) {
        setValue('uart_pin', motor.uart_pin);
      } else {
        setValue('uart_pin', undefined);
      }
      if (motor.cs_pin) {
        setValue('cs_pin', motor.cs_pin);
      } else {
        setValue('cs_pin', undefined);
      }
      if (motor.diag_pin) {
        setValue('diag_pin', motor.diag_pin);
      } else {
        setValue('diag_pin', undefined);
      }
    }
  };

  // Handle individual pin changes from PinEditor
  const handlePinChange = (pinType: string, value: string) => {
    if (!value) {
      setValue(pinType, undefined);
    } else {
      setValue(pinType, value);
    }
  };

  // Track which board endstop is connected to
  const endstopLocation = getValue('endstop_location') ?? 'mainboard';
  const activeEndstopBoardData = endstopLocation === 'toolboard' && toolboardData ? toolboardData : boardData;

  // Handle endstop location change
  const handleEndstopLocationChange = (location: 'mainboard' | 'toolboard') => {
    setValue('endstop_location', location);
    // Clear port selection when switching boards
    setValue('endstop_port', undefined);
    setValue('endstop_pin', undefined);
  };

  // Handle endstop port selection
  const handleEndstopPortChange = (portId: string, portData?: MotorPort | SimplePort | ProbePort) => {
    if (!portId) {
      setValue('endstop_port', undefined);
      setValue('endstop_pin', undefined);
      return;
    }

    setValue('endstop_port', portId);
    setValue('endstop_location', endstopLocation);
    if (portData && 'pin' in portData) {
      const prefix = endstopLocation === 'toolboard' ? 'toolboard:' : '';
      // Endstops typically need pullup
      setValue('endstop_pin', `^${prefix}${(portData as SimplePort).pin}`);
    }
  };

  const selectedDriver = DRIVER_TYPES.find((d) => d.id === getValue('driver_type', 'tmc2209'));

  return (
    <ConfigPanel title={`Stepper ${displayName}`} onClose={() => setActivePanel(null)}>
      <div className="space-y-6">
        {/* Info Banner */}
        <div className="bg-blue-900/30 border border-blue-700 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <Settings className="text-blue-400 shrink-0 mt-0.5" size={20} />
            <div>
              <div className="text-sm font-medium text-blue-300">{displayName} Axis Stepper</div>
              <p className="text-xs text-blue-200/70 mt-1">
                {isZAxis
                  ? 'Configure Z-axis motor. Typically uses lower current and lead screw rotation distance.'
                  : 'Configure XY motion motor. Select the driver port and set appropriate current.'}
              </p>
            </div>
          </div>
        </div>

        {/* Motor Port Selection */}
        <PortSelector
          label="Motor Port"
          portType="motor"
          value={getValue('motor_port') || ''}
          onChange={handleMotorPortChange}
          boardData={boardData}
          usedPorts={portRegistry.getUsedByType('motor')}
          placeholder="Select motor driver port..."
          allowClear={true}
        />

        {/* Editable Pin Configuration */}
        {motorPortData && (
          <PinEditor
            portData={motorPortData}
            pins={currentPins}
            onPinChange={handlePinChange}
            availablePins={availablePins}
            showAdvanced={true}
          />
        )}

        {/* Driver Type */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Driver Type
          </label>
          <select
            value={getValue('driver_type') || ''}
            onChange={(e) => setValue('driver_type', e.target.value || undefined)}
            className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
          >
            <option value="">Select driver type...</option>
            {DRIVER_TYPES.map((driver) => (
              <option key={driver.id} value={driver.id}>
                {driver.name}
              </option>
            ))}
          </select>
          {selectedDriver && (
            <p className="text-xs text-slate-500 mt-1">
              {selectedDriver.description}
              {selectedDriver.sensorless && (
                <span className="ml-2 text-cyan-400">• Supports sensorless homing</span>
              )}
            </p>
          )}
        </div>

        {/* Diag Pin Configuration for SPI/UART drivers */}
        {selectedDriver && selectedDriver.interface !== 'none' && (
          <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4 space-y-3">
            <div className="flex items-start gap-2">
              <Info size={16} className="text-amber-400 shrink-0 mt-0.5" />
              <div>
                <div className="text-sm font-medium text-slate-300">
                  Diag Pin {selectedDriver.interface === 'spi' ? '(Required for SPI)' : '(Optional)'}
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  {selectedDriver.interface === 'spi' 
                    ? 'SPI drivers need the diag pin for sensorless homing AND TMC chopper tuning (StallGuard).'
                    : 'UART drivers can use diag pin for sensorless homing. Connect to an endstop input.'}
                </p>
              </div>
            </div>

            {/* Diag pin from motor port */}
            {motorPortData?.diag_pin && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">diag_pin (from motor port):</span>
                  <code className="text-sm font-mono text-emerald-400 bg-slate-900/50 px-2 py-0.5 rounded">
                    {getValue('diag_pin') || motorPortData.diag_pin}
                  </code>
                </div>

                {/* For SPI drivers, show diag1 and diag0 options */}
                {selectedDriver.interface === 'spi' && (
                  <div className="mt-3 pt-3 border-t border-slate-700">
                    <p className="text-xs text-slate-400 mb-2">
                      SPI drivers have two diag outputs. Configure which to use:
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-xs font-medium text-slate-400 mb-1">
                          diag1_pin (StallGuard) <span className="text-cyan-400">*</span>
                        </label>
                        <input
                          type="text"
                          value={getValue('diag1_pin') || ''}
                          onChange={(e) => setValue('diag1_pin', e.target.value || undefined)}
                          placeholder={motorPortData.diag_pin || 'e.g., PG6'}
                          className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1.5 text-sm text-white placeholder-slate-500 font-mono focus:border-cyan-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-slate-400 mb-1">
                          diag0_pin (optional)
                        </label>
                        <input
                          type="text"
                          value={getValue('diag0_pin') || ''}
                          onChange={(e) => setValue('diag0_pin', e.target.value || undefined)}
                          placeholder="Leave empty if not used"
                          className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1.5 text-sm text-white placeholder-slate-500 font-mono focus:border-cyan-500"
                        />
                      </div>
                    </div>
                    <p className="text-xs text-slate-500 mt-2">
                      <strong>diag1:</strong> Primary output for StallGuard/sensorless homing and chopper tuning.
                      <br />
                      <strong>diag0:</strong> Optional, can be used for overtemperature or other diagnostics.
                    </p>
                  </div>
                )}

                {/* For UART drivers with sensorless support (TMC2209, TMC2226) */}
                {selectedDriver.interface === 'uart' && selectedDriver.sensorless && (
                  <div className="mt-3 pt-3 border-t border-slate-700">
                    <p className="text-xs text-slate-400 mb-2">
                      UART drivers use a single DIAG pin for StallGuard output:
                    </p>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1">
                        diag_pin (StallGuard)
                      </label>
                      <input
                        type="text"
                        value={getValue('diag_pin') || ''}
                        onChange={(e) => setValue('diag_pin', e.target.value || undefined)}
                        placeholder={motorPortData.diag_pin || 'e.g., PG6'}
                        className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1.5 text-sm text-white placeholder-slate-500 font-mono focus:border-cyan-500"
                      />
                    </div>
                    <p className="text-xs text-slate-500 mt-2">
                      Connect DIAG pin to an endstop input for sensorless homing.
                      Required for StallGuard-based homing and chopper tuning.
                    </p>
                    {motorPortData?.diag_pin && !getValue('diag_pin') && (
                      <button
                        type="button"
                        onClick={() => setValue('diag_pin', motorPortData.diag_pin)}
                        className="mt-2 text-xs text-cyan-400 hover:text-cyan-300 underline"
                      >
                        Use {motorPortData.diag_pin} from motor port
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* No diag pin available warning */}
            {!motorPortData?.diag_pin && (
              <div className="text-xs text-amber-400">
                ⚠️ Selected motor port doesn't have a diag pin defined. 
                You may need to wire the diag output to a free GPIO.
              </div>
            )}
          </div>
        )}

        {/* Run Current */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Run Current (A)
          </label>
          <input
            type="number"
            step="0.1"
            min="0.1"
            max="2.5"
            value={getValue('run_current') ?? ''}
            onChange={(e) => {
              const val = e.target.value;
              setValue('run_current', val ? parseFloat(val) : undefined);
            }}
            placeholder={isZAxis ? '0.6' : '0.8'}
            className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
          />
          <div className="flex justify-between text-xs text-slate-500 mt-1">
            <span>0.1A (quiet)</span>
            <span>Typical: {isZAxis ? '0.6A' : '0.8A'}</span>
            <span>2.5A (max)</span>
          </div>
        </div>

        {/* Microsteps */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Microsteps
          </label>
          <div className="grid grid-cols-5 gap-2">
            {MICROSTEP_OPTIONS.map((ms) => (
              <button
                key={ms}
                onClick={() => setValue('microsteps', ms)}
                className={`py-2 rounded-lg text-sm font-medium transition-colors ${
                  getValue('microsteps') === ms
                    ? 'bg-cyan-600 text-white'
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                {ms}
              </button>
            ))}
          </div>
          {!getValue('microsteps') && (
            <p className="text-xs text-slate-500 mt-1">
              <Info size={12} className="inline mr-1" />
              Select microsteps (16 is common default)
            </p>
          )}
        </div>

        {/* Rotation Distance */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Rotation Distance (mm)
          </label>
          <input
            type="number"
            step="0.001"
            min="0.1"
            value={getValue('rotation_distance') ?? ''}
            onChange={(e) => {
              const val = e.target.value;
              setValue('rotation_distance', val ? parseFloat(val) : undefined);
            }}
            placeholder={isZAxis ? '8' : '40'}
            className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
          />
          <p className="text-xs text-slate-500 mt-1">
            {isZAxis
              ? 'Common: 8 (T8 lead screw), 4 (T8 2-start), 40 (belt Z)'
              : 'Common: 40 (GT2 20T), 32 (GT2 16T)'}
          </p>
        </div>

        {/* Endstop Configuration */}
        <div className="space-y-3">
          <label className="block text-sm font-medium text-slate-300">
            Endstop Port
          </label>

          {/* Board selector for endstop (if toolboard enabled) */}
          {toolboardEnabled && toolboardData && (
            <div className="grid grid-cols-2 gap-2 mb-2">
              <button
                onClick={() => handleEndstopLocationChange('mainboard')}
                className={`flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-colors ${
                  endstopLocation === 'mainboard'
                    ? 'bg-cyan-600 text-white'
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                <Cpu size={16} />
                Mainboard
              </button>
              <button
                onClick={() => handleEndstopLocationChange('toolboard')}
                className={`flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-colors ${
                  endstopLocation === 'toolboard'
                    ? 'bg-emerald-600 text-white'
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                <CircuitBoard size={16} />
                Toolboard
              </button>
            </div>
          )}

          <PortSelector
            portType="endstop"
            value={getValue('endstop_port') || ''}
            onChange={handleEndstopPortChange}
            boardData={activeEndstopBoardData}
            usedPorts={portRegistry.getUsedByType('endstop')}
            placeholder={`Select endstop port from ${endstopLocation}...`}
            allowClear={true}
          />
        </div>

        {/* Endstop pin display with pullup/invert toggles */}
        {getValue('endstop_pin') && (
          <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">endstop_pin:</span>
                <code className="text-sm font-mono text-emerald-400">
                  {getValue('endstop_pin')}
                </code>
              </div>
              <div className="flex items-center gap-2">
                {/* Pullup toggle */}
                <button
                  type="button"
                  onClick={() => {
                    const pin = getValue('endstop_pin') || '';
                    const hasInvert = pin.startsWith('!');
                    const hasPullup = pin.includes('^');
                    const base = pin.replace(/^[!^]+/, '');

                    if (hasPullup) {
                      setValue('endstop_pin', hasInvert ? '!' + base : base);
                    } else {
                      setValue('endstop_pin', hasInvert ? '!^' + base : '^' + base);
                    }
                  }}
                  className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
                    (getValue('endstop_pin') || '').includes('^')
                      ? 'bg-cyan-500/20 text-cyan-400'
                      : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                  }`}
                >
                  Pullup
                </button>
                {/* Invert toggle */}
                <button
                  type="button"
                  onClick={() => {
                    const pin = getValue('endstop_pin') || '';
                    if (pin.startsWith('!')) {
                      setValue('endstop_pin', pin.slice(1));
                    } else {
                      setValue('endstop_pin', '!' + pin);
                    }
                  }}
                  className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
                    (getValue('endstop_pin') || '').startsWith('!')
                      ? 'bg-amber-500/20 text-amber-400'
                      : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                  }`}
                >
                  Invert
                </button>
              </div>
            </div>
            <p className="text-xs text-slate-500 mt-2">
              Use <code className="bg-slate-800 px-1 rounded">probe:z_virtual_endstop</code> for Z with probe homing.
            </p>
          </div>
        )}

        {/* Position Max */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Position Max (mm)
          </label>
          <input
            type="number"
            step="1"
            min="1"
            value={getValue('position_max') ?? ''}
            onChange={(e) => {
              const val = e.target.value;
              setValue('position_max', val ? parseInt(val) : undefined);
            }}
            placeholder={isZAxis ? '250' : '235'}
            className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
          />
        </div>

        {/* Homing Direction for non-Z */}
        {!isZAxis && (
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Homing Direction
            </label>
            <div className="grid grid-cols-2 gap-2">
              {['min', 'max'].map((dir) => (
                <button
                  key={dir}
                  onClick={() => setValue('homing_direction', dir)}
                  className={`py-2 rounded-lg text-sm font-medium transition-colors ${
                    getValue('homing_direction') === dir
                      ? 'bg-cyan-600 text-white'
                      : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                  }`}
                >
                  {dir === 'min' ? 'Min (0)' : 'Max (Position Max)'}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </ConfigPanel>
  );
}
