import { useState, useEffect } from 'react';
import { ConfigPanel } from './ConfigPanel';
import useWizardStore from '../../stores/wizardStore';
import { 
  Play, 
  Square, 
  Pause, 
  RotateCcw, 
  Settings2, 
  Thermometer,
  Grid3X3,
  Droplets,
  Clock,
  ParkingCircle,
  Gauge,
  Info
} from 'lucide-react';

// Preset definitions matching CLI wizard
const PRESETS = {
  beginner_safe: {
    name: 'Beginner Safe',
    description: 'Conservative, safety-focused settings for new users',
    settings: {
      extruder_preheat_temp: 150, preheat_scale: 0.75,
      level_bed_at_temp: true, bed_mesh_mode: 'saved',
      probe_temp_source: 'print', bed_stabilize_before_probe: true,
      bed_stabilize_dwell: 0, bed_off_during_probe: false,
      heat_soak_enabled: false, heat_soak_time: 0,
      purge_style: 'line', purge_amount: 30.0,
      brush_enabled: false, heating_park_position: 'center',
      park_position: 'front', pause_heater_off: true, motor_off_delay: 60,
      pause_retract: 1.0, resume_prime: 1.0,
      park_z_hop: 10, end_retract_length: 10, end_retract_speed: 30,
      load_temp: 220, load_length: 100, load_speed: 5, load_prime: 50, load_prime_speed: 2.5,
      unload_length: 100, unload_speed: 30, unload_tip_shape: true,
    }
  },
  voron_style: {
    name: 'Voron-Style',
    description: 'Full workflow with heat soak, brush cleaning, and adaptive mesh',
    settings: {
      extruder_preheat_temp: 150, preheat_scale: 0.75,
      level_bed_at_temp: true, bed_mesh_mode: 'adaptive',
      probe_temp_source: 'print', bed_stabilize_before_probe: true,
      bed_stabilize_dwell: 30, bed_off_during_probe: false,
      heat_soak_enabled: true, heat_soak_time: 15,
      purge_style: 'blob', purge_amount: 30.0,
      brush_enabled: true, wipe_count: 3,
      heating_park_position: 'back', park_position: 'back',
      pause_heater_off: false, motor_off_delay: 300, always_home_z: true,
      pause_retract: 1.0, resume_prime: 1.0,
      park_z_hop: 10, end_retract_length: 10, end_retract_speed: 30,
      load_temp: 220, load_length: 100, load_speed: 5, load_prime: 50, load_prime_speed: 2.5,
      unload_length: 100, unload_speed: 30, unload_tip_shape: true,
    }
  },
  speed_optimized: {
    name: 'Speed-Optimized',
    description: 'Minimal start time for fast printing',
    settings: {
      extruder_preheat_temp: 180, preheat_scale: 1.0,
      level_bed_at_temp: false, bed_mesh_mode: 'saved',
      probe_temp_source: 'print', bed_stabilize_before_probe: false,
      bed_stabilize_dwell: 0, bed_off_during_probe: false,
      heat_soak_enabled: false, heat_soak_time: 0,
      purge_style: 'adaptive', purge_amount: 20.0,
      brush_enabled: false, heating_park_position: 'none',
      park_position: 'front', pause_heater_off: false, motor_off_delay: 30,
      pause_retract: 1.0, resume_prime: 1.0,
      park_z_hop: 10, end_retract_length: 10, end_retract_speed: 30,
      load_temp: 220, load_length: 100, load_speed: 5, load_prime: 50, load_prime_speed: 2.5,
      unload_length: 100, unload_speed: 30, unload_tip_shape: true,
    }
  },
  enclosed_hightemp: {
    name: 'Enclosed High-Temp',
    description: 'For ABS/ASA/PC with heat soak and chamber heating',
    settings: {
      extruder_preheat_temp: 150, preheat_scale: 0.6,
      level_bed_at_temp: true, bed_mesh_mode: 'adaptive',
      probe_temp_source: 'fixed', probe_bed_temp: 80,
      bed_stabilize_before_probe: true, bed_stabilize_dwell: 60,
      bed_off_during_probe: false,
      heat_soak_enabled: true, heat_soak_time: 20,
      chamber_temp_default: 50, chamber_timeout: 45,
      purge_style: 'blob', brush_enabled: true,
      wipe_count: 5, heating_park_position: 'back',
      park_position: 'back', pause_heater_off: false,
      turn_off_fans: false, fan_off_delay: 300, motor_off_delay: 600,
      pause_retract: 1.0, resume_prime: 1.0,
      park_z_hop: 10, end_retract_length: 10, end_retract_speed: 30,
      load_temp: 240, load_length: 100, load_speed: 5, load_prime: 50, load_prime_speed: 2.5,
      unload_length: 100, unload_speed: 30, unload_tip_shape: true,
    }
  },
  bed_slinger: {
    name: 'Bed Slinger',
    description: 'Optimized for cartesian printers with moving bed',
    settings: {
      extruder_preheat_temp: 150, preheat_scale: 0.75,
      level_bed_at_temp: true, bed_mesh_mode: 'saved',
      probe_temp_source: 'print', bed_stabilize_before_probe: true,
      bed_stabilize_dwell: 0, bed_off_during_probe: false,
      heat_soak_enabled: false, heat_soak_time: 0,
      purge_style: 'line', brush_enabled: false,
      heating_park_position: 'front', park_position: 'front',
      pause_heater_off: true, motor_off_delay: 120,
      pause_retract: 1.0, resume_prime: 1.0,
      park_z_hop: 10, end_retract_length: 10, end_retract_speed: 30,
      load_temp: 220, load_length: 450, load_speed: 5, load_prime: 50, load_prime_speed: 2.5,
      unload_length: 450, unload_speed: 30, unload_tip_shape: true,
    }
  },
  production: {
    name: 'Production Mode',
    description: 'Balanced settings for batch printing',
    settings: {
      extruder_preheat_temp: 160, preheat_scale: 0.8,
      level_bed_at_temp: true, bed_mesh_mode: 'adaptive',
      probe_temp_source: 'print', bed_stabilize_before_probe: true,
      bed_stabilize_dwell: 10, bed_off_during_probe: false,
      heat_soak_enabled: false, heat_soak_time: 5,
      purge_style: 'adaptive', purge_amount: 25.0,
      heating_park_position: 'back', park_position: 'back',
      pause_heater_off: false, pause_timeout: 86400, motor_off_delay: 600,
      brush_enabled: false,
      pause_retract: 1.0, resume_prime: 1.0,
      park_z_hop: 10, end_retract_length: 10, end_retract_speed: 30,
      load_temp: 220, load_length: 100, load_speed: 5, load_prime: 50, load_prime_speed: 2.5,
      unload_length: 100, unload_speed: 30, unload_tip_shape: true,
    }
  },
};

type PresetKey = keyof typeof PRESETS;
type TabId = 'presets' | 'start_print' | 'end_print' | 'pause_resume' | 'filament';

const TABS: { id: TabId; label: string; icon: typeof Play }[] = [
  { id: 'presets', label: 'Presets', icon: Settings2 },
  { id: 'start_print', label: 'START_PRINT', icon: Play },
  { id: 'end_print', label: 'END_PRINT', icon: Square },
  { id: 'pause_resume', label: 'PAUSE/RESUME', icon: Pause },
  { id: 'filament', label: 'Filament', icon: RotateCcw },
];

const PARK_POSITIONS = [
  { id: 'front', name: 'Front center' },
  { id: 'back', name: 'Back center' },
  { id: 'center', name: 'Bed center' },
  { id: 'front_left', name: 'Front left' },
  { id: 'front_right', name: 'Front right' },
  { id: 'back_left', name: 'Back left' },
  { id: 'back_right', name: 'Back right' },
  { id: 'none', name: 'None (stay in place)' },
];

const BED_MESH_MODES = [
  { id: 'adaptive', name: 'Adaptive', description: 'Mesh print area only (fast)' },
  { id: 'full', name: 'Full', description: 'Complete bed mesh' },
  { id: 'saved', name: 'Saved', description: 'Load default profile (fastest)' },
  { id: 'none', name: 'None', description: 'Skip meshing' },
];

const PURGE_STYLES = [
  { id: 'line', name: 'Line', description: 'Simple purge line' },
  { id: 'adaptive', name: 'Adaptive', description: 'Near print area (KAMP-style)' },
  { id: 'blob', name: 'Blob', description: 'Bucket purge' },
  { id: 'voron', name: 'Voron', description: 'Full decontamination (bucket+brush)' },
  { id: 'none', name: 'None', description: 'Skip purging' },
];

const PROBE_TEMP_SOURCES = [
  { id: 'print', name: 'Print temp', description: 'Use full BED temperature' },
  { id: 'initial_layer', name: 'Initial layer', description: 'Use BED_INITIAL parameter' },
  { id: 'fixed', name: 'Fixed temp', description: 'Use fixed probe temperature' },
];

export function MacrosPanel() {
  const setActivePanel = useWizardStore((state) => state.setActivePanel);
  const setField = useWizardStore((state) => state.setField);
  const state = useWizardStore((state) => state.state);
  
  const [activeTab, setActiveTab] = useState<TabId>('presets');

  const getValue = (key: string, defaultVal: any = '') => {
    const val = state[`macros.${key}`];
    return val !== undefined ? val : defaultVal;
  };

  const setValue = (key: string, value: any) => {
    setField(`macros.${key}`, value);
  };

  // Apply a preset
  const applyPreset = (presetKey: PresetKey) => {
    const preset = PRESETS[presetKey];
    Object.entries(preset.settings).forEach(([key, value]) => {
      setValue(key, value);
    });
    setValue('preset', presetKey);
  };

  // Apply smart defaults on mount if no preset is set
  useEffect(() => {
    if (!getValue('preset')) {
      // Apply smart defaults based on hardware config
      const kinematics = state['printer.kinematics'] || 'cartesian';
      const extruderType = state['extruder.type'] || '';
      
      let suggestedPreset: PresetKey = 'beginner_safe';
      
      if (kinematics === 'corexy' || kinematics === 'hybrid_corexy') {
        suggestedPreset = 'voron_style';
      } else if (kinematics === 'cartesian') {
        suggestedPreset = 'bed_slinger';
      }
      
      // Check for chamber sensor
      const hasChamber = state['temperature_sensors.chamber.enabled'];
      if (hasChamber) {
        suggestedPreset = 'enclosed_hightemp';
      }
      
      // Apply the suggested preset as initial values
      applyPreset(suggestedPreset);
      
      // Override filament lengths for bowden setups
      const isBowden = extruderType.toLowerCase().includes('bowden');
      if (isBowden) {
        setValue('load_length', 450);
        setValue('unload_length', 450);
      }
      
      // Set park positions based on kinematics
      if (kinematics === 'corexy' || kinematics === 'hybrid_corexy') {
        setValue('park_position', 'back');
        setValue('pause_position', 'back');
        setValue('heating_park_position', 'back');
      } else if (kinematics === 'cartesian') {
        setValue('park_position', 'front');
        setValue('pause_position', 'front');
        setValue('heating_park_position', 'front');
      }
    }
  }, []);

  const currentPreset = getValue('preset', 'beginner_safe');

  return (
    <ConfigPanel title="Macros" onClose={() => setActivePanel(null)} className="w-[480px]">
      <div className="space-y-4">
        {/* Info box */}
        <div className="bg-purple-900/30 border border-purple-700 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <Play className="text-purple-400 shrink-0 mt-0.5" size={20} />
            <div>
              <div className="text-sm font-medium text-purple-300">Print Macros</div>
              <p className="text-xs text-purple-200/70 mt-1">
                Configure START_PRINT, END_PRINT, PAUSE/RESUME, and filament handling macros.
              </p>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-slate-800 rounded-lg p-1">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 px-2 rounded-md text-xs font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-purple-600 text-white'
                  : 'text-slate-400 hover:text-white hover:bg-slate-700'
              }`}
            >
              <tab.icon size={14} />
              <span className="hidden sm:inline">{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="space-y-4">
          {/* Presets Tab */}
          {activeTab === 'presets' && (
            <div className="space-y-4">
              <p className="text-sm text-slate-400">
                Select a preset to apply recommended settings for your setup. You can customize individual settings afterward.
              </p>
              
              <div className="space-y-2">
                {(Object.entries(PRESETS) as [PresetKey, typeof PRESETS[PresetKey]][]).map(([key, preset]) => (
                  <button
                    key={key}
                    onClick={() => applyPreset(key)}
                    className={`w-full text-left p-3 rounded-lg border transition-colors ${
                      currentPreset === key
                        ? 'bg-purple-900/50 border-purple-500'
                        : 'bg-slate-800 border-slate-700 hover:border-slate-600'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className={`font-medium ${currentPreset === key ? 'text-purple-300' : 'text-white'}`}>
                        {preset.name}
                      </span>
                      {currentPreset === key && (
                        <span className="text-xs bg-purple-600 px-2 py-0.5 rounded text-white">Active</span>
                      )}
                    </div>
                    <p className="text-xs text-slate-400 mt-1">{preset.description}</p>
                  </button>
                ))}
              </div>
              
              {currentPreset === 'custom' && (
                <div className="bg-amber-900/30 border border-amber-700 rounded-lg p-3">
                  <p className="text-xs text-amber-200">
                    Custom settings applied. Select a preset to reset to defaults.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* START_PRINT Tab */}
          {activeTab === 'start_print' && (
            <div className="space-y-6">
              {/* Preheat Settings */}
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-slate-300 flex items-center gap-2">
                  <Thermometer size={16} className="text-orange-400" />
                  Preheat Settings
                </h4>
                
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Preheat Temp (C)
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="300"
                      value={getValue('extruder_preheat_temp', 150)}
                      onChange={(e) => { setValue('extruder_preheat_temp', parseInt(e.target.value)); setValue('preset', 'custom'); }}
                      className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                    />
                    <p className="text-xs text-slate-500 mt-1">Max during bed heating</p>
                  </div>
                  
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Preheat Scale
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="1"
                      step="0.05"
                      value={getValue('preheat_scale', 0.75)}
                      onChange={(e) => { setValue('preheat_scale', parseFloat(e.target.value)); setValue('preset', 'custom'); }}
                      className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                    />
                    <p className="text-xs text-slate-500 mt-1">0=off, 1=full</p>
                  </div>
                </div>

                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={getValue('level_bed_at_temp', true)}
                    onChange={(e) => { setValue('level_bed_at_temp', e.target.checked); setValue('preset', 'custom'); }}
                    className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-purple-500 focus:ring-purple-500"
                  />
                  <div>
                    <span className="text-sm text-slate-300">Level bed at temperature</span>
                    <p className="text-xs text-slate-500">Wait for bed temp before leveling (more accurate)</p>
                  </div>
                </label>
              </div>

              {/* Bed Mesh */}
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-slate-300 flex items-center gap-2">
                  <Grid3X3 size={16} className="text-cyan-400" />
                  Bed Mesh Mode
                </h4>
                
                <div className="grid grid-cols-2 gap-2">
                  {BED_MESH_MODES.map((mode) => (
                    <button
                      key={mode.id}
                      onClick={() => { setValue('bed_mesh_mode', mode.id); setValue('preset', 'custom'); }}
                      className={`p-2 rounded-lg text-left transition-colors ${
                        getValue('bed_mesh_mode', 'adaptive') === mode.id
                          ? 'bg-cyan-900/50 border border-cyan-500'
                          : 'bg-slate-800 border border-slate-700 hover:border-slate-600'
                      }`}
                    >
                      <div className="text-sm font-medium text-white">{mode.name}</div>
                      <p className="text-xs text-slate-400">{mode.description}</p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Purge Settings */}
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-slate-300 flex items-center gap-2">
                  <Droplets size={16} className="text-blue-400" />
                  Purge Settings
                </h4>
                
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-2">
                    Purge Style
                  </label>
                  <select
                    value={getValue('purge_style', 'line')}
                    onChange={(e) => { setValue('purge_style', e.target.value); setValue('preset', 'custom'); }}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                  >
                    {PURGE_STYLES.map((style) => (
                      <option key={style.id} value={style.id}>
                        {style.name} - {style.description}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">
                    Purge Amount (mm)
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={getValue('purge_amount', 30)}
                    onChange={(e) => { setValue('purge_amount', parseFloat(e.target.value)); setValue('preset', 'custom'); }}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                  />
                </div>
              </div>

              {/* Heat Soak */}
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-slate-300 flex items-center gap-2">
                  <Clock size={16} className="text-amber-400" />
                  Heat Soak
                </h4>
                
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={getValue('heat_soak_enabled', false)}
                    onChange={(e) => { setValue('heat_soak_enabled', e.target.checked); setValue('preset', 'custom'); }}
                    className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-purple-500 focus:ring-purple-500"
                  />
                  <div>
                    <span className="text-sm text-slate-300">Enable heat soak</span>
                    <p className="text-xs text-slate-500">Stabilize bed/chamber before printing (ABS/ASA)</p>
                  </div>
                </label>

                {getValue('heat_soak_enabled') && (
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Heat Soak Time (minutes)
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="60"
                      value={getValue('heat_soak_time', 10)}
                      onChange={(e) => { setValue('heat_soak_time', parseInt(e.target.value)); setValue('preset', 'custom'); }}
                      className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                    />
                  </div>
                )}
              </div>

              {/* Heating Park Position */}
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-slate-300 flex items-center gap-2">
                  <ParkingCircle size={16} className="text-green-400" />
                  Heating Park Position
                </h4>
                <p className="text-xs text-slate-500">Where to wait during final extruder heating</p>
                
                <select
                  value={getValue('heating_park_position', 'center')}
                  onChange={(e) => { setValue('heating_park_position', e.target.value); setValue('preset', 'custom'); }}
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                >
                  {PARK_POSITIONS.map((pos) => (
                    <option key={pos.id} value={pos.id}>{pos.name}</option>
                  ))}
                </select>
              </div>

              {/* Probe Temperature */}
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-slate-300 flex items-center gap-2">
                  <Gauge size={16} className="text-violet-400" />
                  Probe Temperature
                </h4>
                
                <select
                  value={getValue('probe_temp_source', 'print')}
                  onChange={(e) => { setValue('probe_temp_source', e.target.value); setValue('preset', 'custom'); }}
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                >
                  {PROBE_TEMP_SOURCES.map((src) => (
                    <option key={src.id} value={src.id}>{src.name} - {src.description}</option>
                  ))}
                </select>

                {getValue('probe_temp_source') === 'fixed' && (
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Fixed Probe Temp (C)
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="120"
                      value={getValue('probe_bed_temp', 60)}
                      onChange={(e) => { setValue('probe_bed_temp', parseInt(e.target.value)); setValue('preset', 'custom'); }}
                      className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                    />
                  </div>
                )}

                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">
                    Stabilization Dwell (seconds)
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="120"
                    value={getValue('bed_stabilize_dwell', 0)}
                    onChange={(e) => { setValue('bed_stabilize_dwell', parseInt(e.target.value)); setValue('preset', 'custom'); }}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                  />
                  <p className="text-xs text-slate-500 mt-1">Wait after temp reached for thermal equilibrium</p>
                </div>
              </div>

              {/* Nozzle Brush */}
              <div className="space-y-3">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={getValue('brush_enabled', false)}
                    onChange={(e) => { setValue('brush_enabled', e.target.checked); setValue('preset', 'custom'); }}
                    className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-purple-500 focus:ring-purple-500"
                  />
                  <div>
                    <span className="text-sm text-slate-300">Enable nozzle brush cleaning</span>
                    <p className="text-xs text-slate-500">Requires brush station on printer</p>
                  </div>
                </label>

                {getValue('brush_enabled') && (
                  <div className="grid grid-cols-2 gap-3 pl-7">
                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1">Brush X</label>
                      <input
                        type="number"
                        value={getValue('brush_x', 50)}
                        onChange={(e) => { setValue('brush_x', parseFloat(e.target.value)); setValue('preset', 'custom'); }}
                        className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1">Brush Y</label>
                      <input
                        type="number"
                        value={getValue('brush_y', 300)}
                        onChange={(e) => { setValue('brush_y', parseFloat(e.target.value)); setValue('preset', 'custom'); }}
                        className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1">Brush Z</label>
                      <input
                        type="number"
                        step="0.1"
                        value={getValue('brush_z', 1)}
                        onChange={(e) => { setValue('brush_z', parseFloat(e.target.value)); setValue('preset', 'custom'); }}
                        className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1">Width</label>
                      <input
                        type="number"
                        value={getValue('brush_width', 30)}
                        onChange={(e) => { setValue('brush_width', parseFloat(e.target.value)); setValue('preset', 'custom'); }}
                        className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1">Wipe Count</label>
                      <input
                        type="number"
                        min="1"
                        max="10"
                        value={getValue('wipe_count', 3)}
                        onChange={(e) => { setValue('wipe_count', parseInt(e.target.value)); setValue('preset', 'custom'); }}
                        className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* END_PRINT Tab */}
          {activeTab === 'end_print' && (
            <div className="space-y-6">
              {/* Park Position */}
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-slate-300 flex items-center gap-2">
                  <ParkingCircle size={16} className="text-green-400" />
                  End Print Park Position
                </h4>
                
                <select
                  value={getValue('park_position', 'front')}
                  onChange={(e) => { setValue('park_position', e.target.value); setValue('preset', 'custom'); }}
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                >
                  {PARK_POSITIONS.filter(p => p.id !== 'none').map((pos) => (
                    <option key={pos.id} value={pos.id}>{pos.name}</option>
                  ))}
                </select>

                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">
                    Z Hop (mm)
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="50"
                    value={getValue('park_z_hop', 10)}
                    onChange={(e) => { setValue('park_z_hop', parseFloat(e.target.value)); setValue('preset', 'custom'); }}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                  />
                  <p className="text-xs text-slate-500 mt-1">Lift before parking</p>
                </div>
              </div>

              {/* Retraction */}
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-slate-300">End Print Retraction</h4>
                
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Retract Length (mm)
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="50"
                      value={getValue('end_retract_length', 10)}
                      onChange={(e) => { setValue('end_retract_length', parseFloat(e.target.value)); setValue('preset', 'custom'); }}
                      className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Retract Speed (mm/s)
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="100"
                      value={getValue('end_retract_speed', 30)}
                      onChange={(e) => { setValue('end_retract_speed', parseFloat(e.target.value)); setValue('preset', 'custom'); }}
                      className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                    />
                  </div>
                </div>
              </div>

              {/* Cooldown */}
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-slate-300">Cooldown</h4>
                
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">
                    Motor Off Delay (seconds)
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="3600"
                    step="30"
                    value={getValue('motor_off_delay', 300)}
                    onChange={(e) => { setValue('motor_off_delay', parseInt(e.target.value)); setValue('preset', 'custom'); }}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                  />
                  <p className="text-xs text-slate-500 mt-1">Time before disabling steppers</p>
                </div>
              </div>
            </div>
          )}

          {/* PAUSE/RESUME Tab */}
          {activeTab === 'pause_resume' && (
            <div className="space-y-6">
              {/* Pause Settings */}
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-slate-300 flex items-center gap-2">
                  <Pause size={16} className="text-yellow-400" />
                  Pause Behavior
                </h4>
                
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">
                    Pause Retract (mm)
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="10"
                    step="0.5"
                    value={getValue('pause_retract', 1)}
                    onChange={(e) => { setValue('pause_retract', parseFloat(e.target.value)); setValue('preset', 'custom'); }}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                  />
                  <p className="text-xs text-slate-500 mt-1">Small retract before moving</p>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-2">
                    Pause Park Position
                  </label>
                  <select
                    value={getValue('pause_position', 'front')}
                    onChange={(e) => { setValue('pause_position', e.target.value); setValue('preset', 'custom'); }}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                  >
                    {PARK_POSITIONS.filter(p => p.id !== 'none').map((pos) => (
                      <option key={pos.id} value={pos.id}>{pos.name}</option>
                    ))}
                  </select>
                </div>

                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={getValue('pause_heater_off', true)}
                    onChange={(e) => { setValue('pause_heater_off', e.target.checked); setValue('preset', 'custom'); }}
                    className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-purple-500 focus:ring-purple-500"
                  />
                  <div>
                    <span className="text-sm text-slate-300">Turn off hotend when paused</span>
                    <p className="text-xs text-slate-500">Safer (prevents heat creep), but slower resume</p>
                  </div>
                </label>
              </div>

              {/* Resume Settings */}
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-slate-300 flex items-center gap-2">
                  <Play size={16} className="text-green-400" />
                  Resume Behavior
                </h4>
                
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">
                    Resume Prime (mm)
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="10"
                    step="0.5"
                    value={getValue('resume_prime', 1)}
                    onChange={(e) => { setValue('resume_prime', parseFloat(e.target.value)); setValue('preset', 'custom'); }}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                  />
                  <p className="text-xs text-slate-500 mt-1">Extrusion before resuming print</p>
                </div>
              </div>
            </div>
          )}

          {/* Filament Tab */}
          {activeTab === 'filament' && (
            <div className="space-y-6">
              {/* Info */}
              <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
                <div className="flex items-start gap-2">
                  <Info size={16} className="text-slate-400 shrink-0 mt-0.5" />
                  <p className="text-xs text-slate-400">
                    Configure LOAD_FILAMENT and UNLOAD_FILAMENT macros. Direct drive typically needs 50-100mm, Bowden needs 400-600mm.
                  </p>
                </div>
              </div>

              {/* Load Settings */}
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-slate-300">LOAD_FILAMENT</h4>
                
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">
                    Load Temperature (C)
                  </label>
                  <input
                    type="number"
                    min="150"
                    max="300"
                    value={getValue('load_temp', 220)}
                    onChange={(e) => { setValue('load_temp', parseInt(e.target.value)); setValue('preset', 'custom'); }}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Load Length (mm)
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="800"
                      value={getValue('load_length', 100)}
                      onChange={(e) => { setValue('load_length', parseInt(e.target.value)); setValue('preset', 'custom'); }}
                      className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                    />
                    <p className="text-xs text-slate-500 mt-1">Fast move distance</p>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Load Speed (mm/s)
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="20"
                      value={getValue('load_speed', 5)}
                      onChange={(e) => { setValue('load_speed', parseFloat(e.target.value)); setValue('preset', 'custom'); }}
                      className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Prime Length (mm)
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="100"
                      value={getValue('load_prime', 50)}
                      onChange={(e) => { setValue('load_prime', parseInt(e.target.value)); setValue('preset', 'custom'); }}
                      className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                    />
                    <p className="text-xs text-slate-500 mt-1">Slow extrusion</p>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Prime Speed (mm/s)
                    </label>
                    <input
                      type="number"
                      min="0.5"
                      max="10"
                      step="0.5"
                      value={getValue('load_prime_speed', 2.5)}
                      onChange={(e) => { setValue('load_prime_speed', parseFloat(e.target.value)); setValue('preset', 'custom'); }}
                      className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                    />
                  </div>
                </div>
              </div>

              {/* Unload Settings */}
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-slate-300">UNLOAD_FILAMENT</h4>
                
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Unload Length (mm)
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="800"
                      value={getValue('unload_length', 100)}
                      onChange={(e) => { setValue('unload_length', parseInt(e.target.value)); setValue('preset', 'custom'); }}
                      className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Unload Speed (mm/s)
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="60"
                      value={getValue('unload_speed', 30)}
                      onChange={(e) => { setValue('unload_speed', parseFloat(e.target.value)); setValue('preset', 'custom'); }}
                      className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-purple-500"
                    />
                  </div>
                </div>

                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={getValue('unload_tip_shape', true)}
                    onChange={(e) => { setValue('unload_tip_shape', e.target.checked); setValue('preset', 'custom'); }}
                    className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-purple-500 focus:ring-purple-500"
                  />
                  <div>
                    <span className="text-sm text-slate-300">Enable tip shaping</span>
                    <p className="text-xs text-slate-500">Reduce stringing during unload</p>
                  </div>
                </label>
              </div>
            </div>
          )}
        </div>
      </div>
    </ConfigPanel>
  );
}
