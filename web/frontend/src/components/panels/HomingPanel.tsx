import { ConfigPanel } from './ConfigPanel';
import useWizardStore from '../../stores/wizardStore';
import { Home, Info, Crosshair, AlertTriangle } from 'lucide-react';

// Homing methods from skeleton.json exclusive_groups
const HOMING_METHODS = [
  {
    id: 'safe_z_home',
    name: 'Safe Z Home',
    description: 'Standard safe_z_home - moves to XY position before Z homing',
    compatible: ['all'],
  },
  {
    id: 'beacon_contact',
    name: 'Beacon Contact',
    description: 'Uses Beacon contact mode for Z homing',
    compatible: ['beacon'],
    requiresMode: 'contact',
  },
  {
    id: 'cartographer_touch',
    name: 'Cartographer Touch',
    description: 'Uses Cartographer touch mode for Z homing',
    compatible: ['cartographer'],
    requiresMode: 'touch',
  },
];

export function HomingPanel() {
  const setActivePanel = useWizardStore((state) => state.setActivePanel);
  const setField = useWizardStore((state) => state.setField);
  const state = useWizardStore((state) => state.state);

  const getValue = (key: string, defaultVal?: any) => {
    const val = state[`homing.${key}`];
    return val !== undefined ? val : defaultVal;
  };
  const setValue = (key: string, value: any) => setField(`homing.${key}`, value);

  // Get probe info to determine available homing methods
  const probeType = state['probe.probe_type'];
  const probeMode = state['probe.homing_mode'] || state['probe.home_method'];

  // Get bed size for calculating default home position
  const bedSizeX = state['printer.bed_size_x'];
  const bedSizeY = state['printer.bed_size_y'];

  // Determine which homing methods are available based on probe
  const getAvailableMethods = () => {
    if (!probeType || probeType === 'none' || probeType === 'manual') {
      // No probe or manual endstop - only safe_z_home or no homing section
      return HOMING_METHODS.filter((m) => m.id === 'safe_z_home');
    }

    if (probeType === 'beacon') {
      if (probeMode === 'contact') {
        return [
          HOMING_METHODS.find((m) => m.id === 'beacon_contact')!,
          HOMING_METHODS.find((m) => m.id === 'safe_z_home')!,
        ];
      }
      return HOMING_METHODS.filter((m) => m.id === 'safe_z_home');
    }

    if (probeType === 'cartographer') {
      if (probeMode === 'touch') {
        return [
          HOMING_METHODS.find((m) => m.id === 'cartographer_touch')!,
          HOMING_METHODS.find((m) => m.id === 'safe_z_home')!,
        ];
      }
      return HOMING_METHODS.filter((m) => m.id === 'safe_z_home');
    }

    // All other probes use safe_z_home
    return HOMING_METHODS.filter((m) => m.id === 'safe_z_home');
  };

  const availableMethods = getAvailableMethods();
  const selectedMethod = getValue('homing_method', 'safe_z_home');

  // Auto-calculate center of bed if not set
  const homeX = getValue('home_xy_position_x') ?? (bedSizeX ? Math.round(bedSizeX / 2) : undefined);
  const homeY = getValue('home_xy_position_y') ?? (bedSizeY ? Math.round(bedSizeY / 2) : undefined);

  // Determine if safe_z_home position fields should be shown
  const showSafeZHomePosition = selectedMethod === 'safe_z_home';

  return (
    <ConfigPanel title="Homing Configuration" onClose={() => setActivePanel(null)}>
      <div className="space-y-6">
        {/* Info Banner */}
        <div className="bg-indigo-900/30 border border-indigo-700 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <Home className="text-indigo-400 shrink-0 mt-0.5" size={20} />
            <div>
              <div className="text-sm font-medium text-indigo-300">Z Homing Configuration</div>
              <p className="text-xs text-indigo-200/70 mt-1">
                Configure how your printer homes the Z axis. The available options depend on
                your probe type and configuration.
              </p>
            </div>
          </div>
        </div>

        {/* Probe Status Info */}
        {probeType && probeType !== 'none' && probeType !== 'manual' && (
          <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700">
            <div className="flex items-center gap-2">
              <Crosshair size={16} className="text-violet-400" />
              <span className="text-sm text-slate-300">
                Probe: <span className="font-medium capitalize">{probeType}</span>
                {probeMode && <span className="text-slate-500"> ({probeMode} mode)</span>}
              </span>
            </div>
          </div>
        )}

        {/* No Probe Warning */}
        {(!probeType || probeType === 'none' || probeType === 'manual') && (
          <div className="bg-amber-900/20 border border-amber-700/50 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="text-amber-400 shrink-0 mt-0.5" size={18} />
              <div>
                <div className="text-sm font-medium text-amber-300">No Probe Configured</div>
                <p className="text-xs text-amber-200/70 mt-1">
                  {probeType === 'manual'
                    ? 'Using manual Z endstop. Safe Z Home will be used if you have a separate probe for bed mesh.'
                    : 'Configure a probe first for Z homing with virtual endstop, or use a physical Z endstop switch.'}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Homing Method Selection */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-3">
            Z Homing Method
          </label>
          <div className="space-y-2">
            {availableMethods.map((method) => (
              <button
                key={method.id}
                onClick={() => setValue('homing_method', method.id)}
                className={`w-full p-4 rounded-lg border text-left transition-all ${
                  selectedMethod === method.id
                    ? 'bg-indigo-600/20 border-indigo-500 ring-1 ring-indigo-500'
                    : 'bg-slate-800/50 border-slate-700 hover:border-slate-600'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                      selectedMethod === method.id
                        ? 'border-indigo-500 bg-indigo-500'
                        : 'border-slate-500'
                    }`}
                  >
                    {selectedMethod === method.id && (
                      <div className="w-2 h-2 rounded-full bg-white" />
                    )}
                  </div>
                  <div>
                    <div className="text-sm font-medium text-slate-200">{method.name}</div>
                    <div className="text-xs text-slate-400 mt-0.5">{method.description}</div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Safe Z Home Position (only for safe_z_home method) */}
        {showSafeZHomePosition && (
          <div className="border-t border-slate-700 pt-4">
            <h3 className="text-sm font-medium text-slate-300 mb-3">Safe Z Home Position</h3>
            <p className="text-xs text-slate-500 mb-4">
              XY position where the printer will move before homing Z (typically center of bed)
            </p>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Home X</label>
                <input
                  type="number"
                  step="1"
                  value={homeX ?? ''}
                  onChange={(e) =>
                    setValue('home_xy_position_x', e.target.value ? parseInt(e.target.value) : undefined)
                  }
                  placeholder={bedSizeX ? `${Math.round(bedSizeX / 2)} (center)` : 'e.g., 150'}
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm placeholder-slate-500 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Home Y</label>
                <input
                  type="number"
                  step="1"
                  value={homeY ?? ''}
                  onChange={(e) =>
                    setValue('home_xy_position_y', e.target.value ? parseInt(e.target.value) : undefined)
                  }
                  placeholder={bedSizeY ? `${Math.round(bedSizeY / 2)} (center)` : 'e.g., 150'}
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm placeholder-slate-500 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
                />
              </div>
            </div>

            {bedSizeX && bedSizeY && (
              <p className="text-xs text-slate-500 mt-2">
                Bed size: {bedSizeX}x{bedSizeY}mm — Center: {Math.round(bedSizeX / 2)}, {Math.round(bedSizeY / 2)}
              </p>
            )}
          </div>
        )}

        {/* Beacon Contact Settings */}
        {selectedMethod === 'beacon_contact' && (
          <div className="border-t border-slate-700 pt-4">
            <h3 className="text-sm font-medium text-slate-300 mb-3">Beacon Contact Settings</h3>

            <div className="bg-emerald-900/20 border border-emerald-700/50 rounded-lg p-3 mb-4">
              <div className="flex items-start gap-2">
                <Info size={14} className="text-emerald-400 shrink-0 mt-0.5" />
                <div className="text-xs text-emerald-300">
                  Beacon contact homing uses the probe's contact detection for accurate Z homing.
                  Configure contact settings in the Probe panel.
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Cartographer Touch Settings */}
        {selectedMethod === 'cartographer_touch' && (
          <div className="border-t border-slate-700 pt-4">
            <h3 className="text-sm font-medium text-slate-300 mb-3">Cartographer Touch Settings</h3>

            <div className="bg-emerald-900/20 border border-emerald-700/50 rounded-lg p-3 mb-4">
              <div className="flex items-start gap-2">
                <Info size={14} className="text-emerald-400 shrink-0 mt-0.5" />
                <div className="text-xs text-emerald-300">
                  Cartographer touch homing uses the probe's touch detection for Z homing.
                  Configure touch settings in the Probe panel.
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Homing Speed Settings */}
        <div className="border-t border-slate-700 pt-4">
          <h3 className="text-sm font-medium text-slate-300 mb-3">Homing Speed</h3>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">
                Z Hop Height (mm)
              </label>
              <input
                type="number"
                step="1"
                min="0"
                value={getValue('z_hop', 10) ?? ''}
                onChange={(e) => setValue('z_hop', e.target.value ? parseFloat(e.target.value) : undefined)}
                placeholder="10"
                className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm placeholder-slate-500 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
              />
              <p className="text-xs text-slate-500 mt-1">Height to raise Z before XY homing</p>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">
                Z Hop Speed (mm/s)
              </label>
              <input
                type="number"
                step="1"
                min="1"
                value={getValue('z_hop_speed', 15) ?? ''}
                onChange={(e) => setValue('z_hop_speed', e.target.value ? parseFloat(e.target.value) : undefined)}
                placeholder="15"
                className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm placeholder-slate-500 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
              />
            </div>
          </div>
        </div>

        {/* Move to Previous Position */}
        <div className="border-t border-slate-700 pt-4">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={getValue('move_to_previous', false)}
              onChange={(e) => setValue('move_to_previous', e.target.checked)}
              className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-indigo-500 focus:ring-indigo-500"
            />
            <div>
              <span className="text-sm text-slate-300">Move to Previous Position</span>
              <p className="text-xs text-slate-500">
                Return to XY position from before homing after Z home completes
              </p>
            </div>
          </label>
        </div>
      </div>
    </ConfigPanel>
  );
}
