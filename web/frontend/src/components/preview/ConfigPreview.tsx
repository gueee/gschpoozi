import { useState, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import useWizardStore from '../../stores/wizardStore';
import { generatorApi } from '../../services/api';
import { useDebounce, useWizardLogic } from '../../hooks';
import { AlertTriangle, CheckCircle, FileText, Loader2, Info, AlertCircle } from 'lucide-react';
import { ConflictsDisplay } from '../ui/ConflictsDisplay';

export function ConfigPreview() {
  const wizardState = useWizardStore((state) => state.state);
  const [files, setFiles] = useState<Record<string, string>>({});
  const [activeFile, setActiveFile] = useState<string>('printer.cfg');
  const [loading, setLoading] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [backendAvailable, setBackendAvailable] = useState(true);
  const [showWarnings, setShowWarnings] = useState(false);
  const [showConflicts, setShowConflicts] = useState(true);

  const debouncedState = useDebounce(wizardState, 500);
  const { conflicts, hasErrors, hasWarnings: hasLogicWarnings, validationSummary } = useWizardLogic();

  useEffect(() => {
    async function generatePreview() {
      // Always generate a preview, even with minimal state
      const kinematics = debouncedState['printer.kinematics'];

      if (!kinematics) {
        setFiles({});
        setWarnings([]);
        return;
      }

      setLoading(true);
      setWarnings([]);

      try {
        const response = await generatorApi.preview(debouncedState);
        setBackendAvailable(true);

        if (response.success && response.files && Object.keys(response.files).length > 0) {
          setFiles(response.files);
          setWarnings(response.warnings || []);
          // Auto-select first file if current doesn't exist
          if (!response.files[activeFile] && Object.keys(response.files).length > 0) {
            setActiveFile(Object.keys(response.files)[0]);
          }
        } else {
          // Backend returned errors - generate local preview instead
          setWarnings(response.errors || []);
          generateLocalPreview(debouncedState);
        }
      } catch (err) {
        if (err instanceof Error && err.message.includes('fetch')) {
          setBackendAvailable(false);
        }
        // Generate local preview as fallback
        generateLocalPreview(debouncedState);
      } finally {
        setLoading(false);
      }
    }

    generatePreview();
  }, [debouncedState, activeFile]);

  // Generate a local preview based on current state
  function generateLocalPreview(state: Record<string, any>) {
    const kinematics = state['printer.kinematics'] || 'cartesian';
    const boardType = state['mcu.main.board_type'] || '';
    const serial = state['mcu.main.serial'] || '/dev/serial/by-id/usb-...';
    const zMotorCount = state['z_config.motor_count'] || 1;

    // Build the main printer.cfg
    let printerCfg = `# ═══════════════════════════════════════════════════════════════════════════
# gschpoozi Klipper Configuration
# Generated for: ${kinematics.replace('_', ' ').toUpperCase()} printer
# ═══════════════════════════════════════════════════════════════════════════

# Include modular configuration files
[include gschpoozi_hardware.cfg]
[include gschpoozi_macros.cfg]
[include gschpoozi_macros-config.cfg]

# User overrides (edit this file for your customizations)
# [include user-overrides.cfg]

# ─────────────────────────────────────────────────────────────────────────────
# Printer Settings
# ─────────────────────────────────────────────────────────────────────────────
[printer]
kinematics: ${kinematics}
max_velocity: ${state['printer.max_velocity'] || 300}
max_accel: ${state['printer.max_accel'] || 3000}
max_z_velocity: ${state['printer.max_z_velocity'] || 15}
max_z_accel: ${state['printer.max_z_accel'] || 100}
square_corner_velocity: ${state['printer.square_corner_velocity'] || 5.0}
`;

    // Build the hardware config
    let hardwareCfg = `# ═══════════════════════════════════════════════════════════════════════════
# Hardware Configuration
# Board: ${boardType || '(not selected)'}
# ═══════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# MCU Configuration
# ─────────────────────────────────────────────────────────────────────────────
[mcu]
serial: ${serial}
# restart_method: command

`;

    // Add X stepper
    hardwareCfg += `# ─────────────────────────────────────────────────────────────────────────────
# X Axis
# ─────────────────────────────────────────────────────────────────────────────
[stepper_x]
step_pin: ${state['stepper_x.step_pin'] || 'PF13  # Configure in MCU panel'}
dir_pin: ${state['stepper_x.dir_pin'] || 'PF12'}
enable_pin: ${state['stepper_x.enable_pin'] || '!PF14'}
rotation_distance: ${state['stepper_x.rotation_distance'] || 40}
microsteps: ${state['stepper_x.microsteps'] || 16}
full_steps_per_rotation: 200
endstop_pin: ${state['stepper_x.endstop_pin'] || 'PG6  # Configure endstop'}
position_endstop: ${state['stepper_x.position_endstop'] || 0}
position_max: ${state['printer.bed_size_x'] || 235}
homing_speed: 50
homing_retract_dist: 5

`;

    // Add TMC config for X
    const xDriverType = state['stepper_x.driver_type'] || 'tmc2209';
    hardwareCfg += `[${xDriverType} stepper_x]
uart_pin: ${state['stepper_x.uart_pin'] || 'PC4'}
run_current: ${state['stepper_x.run_current'] || 0.8}
stealthchop_threshold: 999999

`;

    // Add Y stepper
    hardwareCfg += `# ─────────────────────────────────────────────────────────────────────────────
# Y Axis
# ─────────────────────────────────────────────────────────────────────────────
[stepper_y]
step_pin: ${state['stepper_y.step_pin'] || 'PG0  # Configure in MCU panel'}
dir_pin: ${state['stepper_y.dir_pin'] || 'PG1'}
enable_pin: ${state['stepper_y.enable_pin'] || '!PF15'}
rotation_distance: ${state['stepper_y.rotation_distance'] || 40}
microsteps: ${state['stepper_y.microsteps'] || 16}
full_steps_per_rotation: 200
endstop_pin: ${state['stepper_y.endstop_pin'] || 'PG9  # Configure endstop'}
position_endstop: ${state['stepper_y.position_endstop'] || 0}
position_max: ${state['printer.bed_size_y'] || 235}
homing_speed: 50
homing_retract_dist: 5

`;

    const yDriverType = state['stepper_y.driver_type'] || 'tmc2209';
    hardwareCfg += `[${yDriverType} stepper_y]
uart_pin: ${state['stepper_y.uart_pin'] || 'PD11'}
run_current: ${state['stepper_y.run_current'] || 0.8}
stealthchop_threshold: 999999

`;

    // Add AWD motors if hybrid_corexy
    if (kinematics === 'hybrid_corexy') {
      hardwareCfg += `# ─────────────────────────────────────────────────────────────────────────────
# X1 Axis (AWD - synced with X)
# ─────────────────────────────────────────────────────────────────────────────
[stepper_x1]
step_pin: ${state['stepper_x1.step_pin'] || 'PE2  # Configure motor port'}
dir_pin: ${state['stepper_x1.dir_pin'] || 'PE3'}
enable_pin: ${state['stepper_x1.enable_pin'] || '!PD4'}
rotation_distance: ${state['stepper_x1.rotation_distance'] || state['stepper_x.rotation_distance'] || 40}
microsteps: ${state['stepper_x1.microsteps'] || 16}
full_steps_per_rotation: 200

[${state['stepper_x1.driver_type'] || 'tmc2209'} stepper_x1]
uart_pin: ${state['stepper_x1.uart_pin'] || 'PE1'}
run_current: ${state['stepper_x1.run_current'] || state['stepper_x.run_current'] || 0.8}
stealthchop_threshold: 999999

# ─────────────────────────────────────────────────────────────────────────────
# Y1 Axis (AWD - synced with Y)
# ─────────────────────────────────────────────────────────────────────────────
[stepper_y1]
step_pin: ${state['stepper_y1.step_pin'] || 'PE6  # Configure motor port'}
dir_pin: ${state['stepper_y1.dir_pin'] || '!PA14'}
enable_pin: ${state['stepper_y1.enable_pin'] || '!PE0'}
rotation_distance: ${state['stepper_y1.rotation_distance'] || state['stepper_y.rotation_distance'] || 40}
microsteps: ${state['stepper_y1.microsteps'] || 16}
full_steps_per_rotation: 200

[${state['stepper_y1.driver_type'] || 'tmc2209'} stepper_y1]
uart_pin: ${state['stepper_y1.uart_pin'] || 'PD3'}
run_current: ${state['stepper_y1.run_current'] || state['stepper_y.run_current'] || 0.8}
stealthchop_threshold: 999999

`;
    }

    // Add Z stepper(s) based on count
    hardwareCfg += `# ─────────────────────────────────────────────────────────────────────────────
# Z Axis (${zMotorCount} motor${zMotorCount > 1 ? 's' : ''})
# ─────────────────────────────────────────────────────────────────────────────
[stepper_z]
step_pin: ${state['stepper_z.step_pin'] || 'PF11  # Configure in MCU panel'}
dir_pin: ${state['stepper_z.dir_pin'] || 'PG3'}
enable_pin: ${state['stepper_z.enable_pin'] || '!PG5'}
rotation_distance: ${state['stepper_z.rotation_distance'] || 8}
microsteps: ${state['stepper_z.microsteps'] || 16}
full_steps_per_rotation: 200
endstop_pin: probe:z_virtual_endstop
position_max: ${state['printer.max_z'] || 250}
position_min: -5
homing_speed: 8
second_homing_speed: 3
homing_retract_dist: 3

`;

    const zDriverType = state['stepper_z.driver_type'] || 'tmc2209';
    hardwareCfg += `[${zDriverType} stepper_z]
uart_pin: ${state['stepper_z.uart_pin'] || 'PC6'}
run_current: ${state['stepper_z.run_current'] || 0.6}
stealthchop_threshold: 999999

`;

    // Add additional Z steppers
    for (let i = 1; i < zMotorCount; i++) {
      const zName = `stepper_z${i}`;
      hardwareCfg += `[${zName}]
step_pin: ${state[`${zName}.step_pin`] || `# Configure Z${i} motor port`}
dir_pin: ${state[`${zName}.dir_pin`] || '# Configure'}
enable_pin: ${state[`${zName}.enable_pin`] || '# Configure'}
rotation_distance: ${state[`${zName}.rotation_distance`] || state['stepper_z.rotation_distance'] || 8}
microsteps: ${state[`${zName}.microsteps`] || 16}
full_steps_per_rotation: 200

[${state[`${zName}.driver_type`] || 'tmc2209'} ${zName}]
uart_pin: ${state[`${zName}.uart_pin`] || '# Configure'}
run_current: ${state[`${zName}.run_current`] || state['stepper_z.run_current'] || 0.6}
stealthchop_threshold: 999999

`;
    }

    // Add Z tilt or quad gantry level if multiple Z motors
    if (zMotorCount === 3) {
      hardwareCfg += `# ─────────────────────────────────────────────────────────────────────────────
# Z Tilt Adjustment (3 Z motors)
# ─────────────────────────────────────────────────────────────────────────────
[z_tilt]
z_positions:
    -50, -13    # Rear left
    ${(state['printer.bed_size_x'] || 235) + 50}, -13    # Rear right
    ${(state['printer.bed_size_x'] || 235) / 2}, ${(state['printer.bed_size_y'] || 235) + 50}    # Front center
points:
    30, 30
    ${(state['printer.bed_size_x'] || 235) - 30}, 30
    ${(state['printer.bed_size_x'] || 235) / 2}, ${(state['printer.bed_size_y'] || 235) - 30}
speed: 200
horizontal_move_z: 10
retries: 5
retry_tolerance: 0.0075

`;
    } else if (zMotorCount === 4) {
      hardwareCfg += `# ─────────────────────────────────────────────────────────────────────────────
# Quad Gantry Level (4 Z motors)
# ─────────────────────────────────────────────────────────────────────────────
[quad_gantry_level]
gantry_corners:
    -60, -10
    ${(state['printer.bed_size_x'] || 235) + 60}, ${(state['printer.bed_size_y'] || 235) + 60}
points:
    50, 25
    50, ${(state['printer.bed_size_y'] || 235) - 25}
    ${(state['printer.bed_size_x'] || 235) - 50}, ${(state['printer.bed_size_y'] || 235) - 25}
    ${(state['printer.bed_size_x'] || 235) - 50}, 25
speed: 200
horizontal_move_z: 10
retries: 5
retry_tolerance: 0.0075

`;
    } else if (zMotorCount === 2) {
      hardwareCfg += `# ─────────────────────────────────────────────────────────────────────────────
# Z Tilt Adjustment (2 Z motors)
# ─────────────────────────────────────────────────────────────────────────────
[z_tilt]
z_positions:
    -50, ${(state['printer.bed_size_y'] || 235) / 2}    # Left
    ${(state['printer.bed_size_x'] || 235) + 50}, ${(state['printer.bed_size_y'] || 235) / 2}    # Right
points:
    30, ${(state['printer.bed_size_y'] || 235) / 2}
    ${(state['printer.bed_size_x'] || 235) - 30}, ${(state['printer.bed_size_y'] || 235) / 2}
speed: 200
horizontal_move_z: 10
retries: 5
retry_tolerance: 0.0075

`;
    }

    // Add extruder
    hardwareCfg += `# ─────────────────────────────────────────────────────────────────────────────
# Extruder
# ─────────────────────────────────────────────────────────────────────────────
[extruder]
step_pin: ${state['extruder.step_pin'] || 'PF9  # Configure motor port'}
dir_pin: ${state['extruder.dir_pin'] || '!PF10'}
enable_pin: ${state['extruder.enable_pin'] || '!PG2'}
rotation_distance: ${state['extruder.rotation_distance'] || 22.6789511}
gear_ratio: ${state['extruder.gear_ratio'] || '50:10'}
microsteps: ${state['extruder.microsteps'] || 16}
full_steps_per_rotation: 200
nozzle_diameter: ${state['extruder.nozzle_diameter'] || 0.4}
filament_diameter: 1.750
heater_pin: ${state['extruder.heater_pin'] || 'PA2  # Configure heater'}
sensor_pin: ${state['extruder.sensor_pin'] || 'PF4  # Configure thermistor'}
sensor_type: ${state['extruder.sensor_type'] || 'EPCOS 100K B57560G104F'}${state['extruder.pullup_resistor'] ? `
pullup_resistor: ${state['extruder.pullup_resistor']}` : ''}
min_temp: 0
max_temp: ${state['extruder.max_temp'] || 280}
min_extrude_temp: 170
max_extrude_only_distance: 150
max_extrude_cross_section: 5
pressure_advance: ${state['extruder.pressure_advance'] || 0.04}
pressure_advance_smooth_time: 0.040

`;

    const extruderDriverType = state['extruder.driver_type'] || 'tmc2209';
    hardwareCfg += `[${extruderDriverType} extruder]
uart_pin: ${state['extruder.uart_pin'] || 'PC7'}
run_current: ${state['extruder.run_current'] || 0.5}
stealthchop_threshold: 0

`;

    // Add heater bed
    hardwareCfg += `# ─────────────────────────────────────────────────────────────────────────────
# Heated Bed
# ─────────────────────────────────────────────────────────────────────────────
[heater_bed]
heater_pin: ${state['heater_bed.heater_pin'] || 'PA1  # Configure heater'}
sensor_pin: ${state['heater_bed.sensor_pin'] || 'PF3  # Configure thermistor'}
sensor_type: ${state['heater_bed.sensor_type'] || 'Generic 3950'}
min_temp: 0
max_temp: ${state['heater_bed.max_temp'] || 120}

`;

    // Add probe
    hardwareCfg += `# ─────────────────────────────────────────────────────────────────────────────
# Probe
# ─────────────────────────────────────────────────────────────────────────────
[probe]
pin: ${state['probe.pin'] || '^PG15  # Configure probe pin'}
x_offset: ${state['probe.x_offset'] || 0}
y_offset: ${state['probe.y_offset'] || 0}
#z_offset: 0  # Calibrate with PROBE_CALIBRATE
speed: 5
samples: 3
samples_result: median
sample_retract_dist: 2.0
samples_tolerance: 0.006
samples_tolerance_retries: 3

`;

    // Add bed mesh
    hardwareCfg += `# ─────────────────────────────────────────────────────────────────────────────
# Bed Mesh
# ─────────────────────────────────────────────────────────────────────────────
[bed_mesh]
speed: 200
horizontal_move_z: 5
mesh_min: 30, 30
mesh_max: ${(state['printer.bed_size_x'] || 235) - 30}, ${(state['printer.bed_size_y'] || 235) - 30}
probe_count: 5, 5
algorithm: bicubic
fade_start: 0.6
fade_end: 10.0

`;

    // Add fans
    hardwareCfg += `# ─────────────────────────────────────────────────────────────────────────────
# Fans
# ─────────────────────────────────────────────────────────────────────────────
[fan]
# Part cooling fan
pin: ${state['fans.part_cooling.pin'] || 'PA8  # Configure fan pin'}
max_power: 1.0
kick_start_time: 0.5

[heater_fan hotend_fan]
pin: ${state['fans.hotend.pin'] || 'PE5  # Configure fan pin'}
max_power: 1.0
kick_start_time: 0.5
heater: extruder
heater_temp: 50.0

[controller_fan controller_fan]
pin: ${state['fans.controller.pin'] || 'PD12  # Configure fan pin'}
max_power: 0.5
kick_start_time: 0.5
idle_timeout: 60
stepper: stepper_x, stepper_y

`;

    // Add homing override for safe Z homing
    hardwareCfg += `# ─────────────────────────────────────────────────────────────────────────────
# Safe Z Home
# ─────────────────────────────────────────────────────────────────────────────
[safe_z_home]
home_xy_position: ${(state['printer.bed_size_x'] || 235) / 2}, ${(state['printer.bed_size_y'] || 235) / 2}
speed: 100
z_hop: 10
z_hop_speed: 10
`;

    const mockFiles: Record<string, string> = {
      'printer.cfg': printerCfg,
      'gschpoozi_hardware.cfg': hardwareCfg,
    };

    setFiles(mockFiles);

    // Auto-select first file if needed
    if (!mockFiles[activeFile]) {
      setActiveFile('printer.cfg');
    }
  }

  const fileNames = Object.keys(files);

  return (
    <div className="h-full flex flex-col bg-slate-900">
      {/* Header with status */}
      <div className="flex items-center justify-between px-4 py-2 bg-slate-800 border-b border-slate-700">
        <div className="flex items-center gap-2 text-slate-300">
          <FileText size={16} />
          <span className="text-sm font-medium">Config Preview</span>
          {/* Validation status badge */}
          {validationSummary.completionPercent < 100 && (
            <span className="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-400">
              {validationSummary.completionPercent}% complete
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Conflicts indicator */}
          {hasErrors && (
            <button
              onClick={() => setShowConflicts(!showConflicts)}
              className="flex items-center gap-1 text-red-400 text-xs hover:text-red-300 transition-colors"
            >
              <AlertCircle size={12} />
              <span>{validationSummary.errorCount} error{validationSummary.errorCount > 1 ? 's' : ''}</span>
            </button>
          )}
          {!hasErrors && hasLogicWarnings && (
            <button
              onClick={() => setShowConflicts(!showConflicts)}
              className="flex items-center gap-1 text-amber-400 text-xs hover:text-amber-300 transition-colors"
            >
              <AlertTriangle size={12} />
              <span>{validationSummary.warningCount} warning{validationSummary.warningCount > 1 ? 's' : ''}</span>
            </button>
          )}
          {warnings.length > 0 && (
            <button
              onClick={() => setShowWarnings(!showWarnings)}
              className="flex items-center gap-1 text-amber-400 text-xs hover:text-amber-300 transition-colors"
            >
              <AlertTriangle size={12} />
              <span>{warnings.length} gen warning{warnings.length > 1 ? 's' : ''}</span>
            </button>
          )}
          {!backendAvailable && (
            <div className="flex items-center gap-1 text-amber-400 text-xs">
              <Info size={12} />
              <span>Local preview</span>
            </div>
          )}
          {backendAvailable && !loading && files && Object.keys(files).length > 0 && warnings.length === 0 && !hasErrors && (
            <div className="flex items-center gap-1 text-emerald-400 text-xs">
              <CheckCircle size={12} />
              <span>Live</span>
            </div>
          )}
        </div>
      </div>

      {/* Conflicts panel */}
      {showConflicts && conflicts.length > 0 && (
        <div className="p-3 border-b border-slate-700 max-h-60 overflow-y-auto">
          <ConflictsDisplay
            conflicts={conflicts}
            defaultCollapsed={false}
          />
        </div>
      )}

      {/* Generator warnings panel */}
      {showWarnings && warnings.length > 0 && (
        <div className="p-3 bg-amber-900/30 border-b border-amber-700/50 max-h-40 overflow-y-auto">
          <div className="text-xs text-amber-300 space-y-1">
            {warnings.map((w, i) => (
              <div key={i} className="flex items-start gap-2">
                <span className="text-amber-500">•</span>
                <span>{w}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* File tabs */}
      <div className="flex border-b border-slate-700 bg-slate-800/50 overflow-x-auto">
        {fileNames.map((filename) => (
          <button
            key={filename}
            onClick={() => setActiveFile(filename)}
            className={`px-4 py-2 text-sm whitespace-nowrap transition-colors ${
              activeFile === filename
                ? 'bg-slate-900 text-cyan-400 border-b-2 border-cyan-400 font-medium'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
            }`}
          >
            {filename}
          </button>
        ))}
        {fileNames.length === 0 && (
          <div className="px-4 py-2 text-sm text-slate-500 italic">
            Select kinematics to see preview...
          </div>
        )}
      </div>

      {/* Editor area */}
      <div className="flex-1 relative">
        {loading && (
          <div className="absolute inset-0 bg-slate-900/90 flex items-center justify-center z-10">
            <div className="flex items-center gap-3 text-slate-400">
              <Loader2 className="animate-spin" size={24} />
              <span>Generating preview...</span>
            </div>
          </div>
        )}

        <Editor
          height="100%"
          language="ini"
          value={files[activeFile] || '# Select a kinematics type to generate config preview...'}
          options={{
            readOnly: true,
            minimap: { enabled: false },
            fontSize: 13,
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            wordWrap: 'on',
            fontFamily: 'JetBrains Mono, Fira Code, Monaco, Consolas, monospace',
            padding: { top: 16 },
            renderLineHighlight: 'none',
          }}
          theme="vs-dark"
        />
      </div>
    </div>
  );
}
