import { ConfigPanel } from './ConfigPanel';
import useWizardStore from '../../stores/wizardStore';
import { Layers, Info, AlertTriangle, Grid3X3 } from 'lucide-react';

// Leveling types from skeleton.json exclusive_groups
const LEVELING_TYPES = [
  {
    id: 'none',
    name: 'None (Manual Leveling)',
    description: 'No automatic gantry/bed leveling. Use manual screws.',
    minMotors: 1,
    maxMotors: 99,
    klipperSection: null,
  },
  {
    id: 'z_tilt',
    name: 'Z Tilt Adjust',
    description: 'For 2-3 Z motors. Tilts the Z axis to compensate for an uneven bed.',
    minMotors: 2,
    maxMotors: 3,
    klipperSection: '[z_tilt]',
  },
  {
    id: 'qgl',
    name: 'Quad Gantry Level',
    description: 'For 4 Z motors (Voron 2.4 style). Levels all 4 corners independently.',
    minMotors: 4,
    maxMotors: 4,
    klipperSection: '[quad_gantry_level]',
  },
];

export function BedLevelingPanel() {
  const setActivePanel = useWizardStore((state) => state.setActivePanel);
  const setField = useWizardStore((state) => state.setField);
  const state = useWizardStore((state) => state.state);

  // Bed leveling state
  const getBedLevelingValue = (key: string, defaultVal?: any) => {
    const val = state[`bed_leveling.${key}`];
    return val !== undefined ? val : defaultVal;
  };
  const setBedLevelingValue = (key: string, value: any) => setField(`bed_leveling.${key}`, value);

  // Bed mesh state (stored under probe.bed_mesh)
  const getBedMeshValue = (key: string, defaultVal?: any) => {
    const val = state[`probe.bed_mesh.${key}`];
    return val !== undefined ? val : defaultVal;
  };
  const setBedMeshValue = (key: string, value: any) => setField(`probe.bed_mesh.${key}`, value);

  // Get probe and printer info
  const probeType = state['probe.probe_type'];
  const zMotorCount = state['stepper_z.z_motor_count'] ?? 1;
  const bedSizeX = state['printer.bed_size_x'];
  const bedSizeY = state['printer.bed_size_y'];
  const probeXOffset = state['probe.x_offset'] ?? 0;
  const probeYOffset = state['probe.y_offset'] ?? 0;

  // Determine if probe is available for leveling
  const hasProbe = probeType && probeType !== 'none' && probeType !== 'manual';

  // Determine if this is an eddy probe (can do rapid mesh)
  const isEddyProbe = ['beacon', 'cartographer', 'btt-eddy', 'btt-eddy-coil'].includes(probeType);

  // Filter available leveling types based on Z motor count
  const availableLevelingTypes = LEVELING_TYPES.filter(
    (type) => zMotorCount >= type.minMotors && zMotorCount <= type.maxMotors
  );

  // Auto-select based on motor count if not set
  const selectedType = getBedLevelingValue('leveling_type') ?? 
    (zMotorCount === 4 ? 'qgl' : zMotorCount >= 2 ? 'z_tilt' : 'none');

  // Bed mesh values with auto-calculation
  const meshEnabled = getBedMeshValue('enabled', true);
  const meshMinX = getBedMeshValue('mesh_min_x') ?? Math.max(5, Math.ceil(probeXOffset) + 5);
  const meshMinY = getBedMeshValue('mesh_min_y') ?? Math.max(5, Math.ceil(probeYOffset) + 5);
  const meshMaxX = getBedMeshValue('mesh_max_x') ?? (bedSizeX ? bedSizeX - 5 : undefined);
  const meshMaxY = getBedMeshValue('mesh_max_y') ?? (bedSizeY ? bedSizeY - 5 : undefined);
  const probeCount = getBedMeshValue('probe_count', isEddyProbe ? '25,25' : '5,5');

  return (
    <ConfigPanel title="Bed Leveling & Mesh" onClose={() => setActivePanel(null)}>
      <div className="space-y-6">
        {/* Info Banner */}
        <div className="bg-teal-900/30 border border-teal-700 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <Layers className="text-teal-400 shrink-0 mt-0.5" size={20} />
            <div>
              <div className="text-sm font-medium text-teal-300">Bed Leveling Configuration</div>
              <p className="text-xs text-teal-200/70 mt-1">
                Configure gantry leveling and bed mesh probing. Available options depend on 
                your Z motor count and probe configuration.
              </p>
            </div>
          </div>
        </div>

        {/* Z Motor Info */}
        <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700">
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-300">
              Z Motor Count: <span className="font-medium text-cyan-400">{zMotorCount}</span>
            </span>
            {zMotorCount === 4 && (
              <span className="text-xs bg-violet-500/20 text-violet-300 px-2 py-0.5 rounded">
                QGL Compatible
              </span>
            )}
            {zMotorCount >= 2 && zMotorCount <= 3 && (
              <span className="text-xs bg-cyan-500/20 text-cyan-300 px-2 py-0.5 rounded">
                Z Tilt Compatible
              </span>
            )}
          </div>
        </div>

        {/* No Probe Warning */}
        {!hasProbe && (
          <div className="bg-amber-900/20 border border-amber-700/50 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="text-amber-400 shrink-0 mt-0.5" size={18} />
              <div>
                <div className="text-sm font-medium text-amber-300">No Probe Configured</div>
                <p className="text-xs text-amber-200/70 mt-1">
                  Automatic bed leveling and mesh require a probe. Configure a probe first
                  to enable Z tilt adjust, QGL, and bed mesh.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Leveling Type Selection */}
        {hasProbe && (
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-3">
              Gantry/Bed Leveling Method
            </label>
            <div className="space-y-2">
              {availableLevelingTypes.map((type) => (
                <button
                  key={type.id}
                  onClick={() => setBedLevelingValue('leveling_type', type.id)}
                  className={`w-full p-4 rounded-lg border text-left transition-all ${
                    selectedType === type.id
                      ? 'bg-teal-600/20 border-teal-500 ring-1 ring-teal-500'
                      : 'bg-slate-800/50 border-slate-700 hover:border-slate-600'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                        selectedType === type.id
                          ? 'border-teal-500 bg-teal-500'
                          : 'border-slate-500'
                      }`}
                    >
                      {selectedType === type.id && (
                        <div className="w-2 h-2 rounded-full bg-white" />
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="text-sm font-medium text-slate-200">{type.name}</div>
                      <div className="text-xs text-slate-400 mt-0.5">{type.description}</div>
                    </div>
                    {type.klipperSection && (
                      <code className="text-xs bg-slate-700 text-slate-400 px-1.5 py-0.5 rounded">
                        {type.klipperSection}
                      </code>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Bed Mesh Section */}
        {hasProbe && (
          <div className="border-t border-slate-700 pt-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Grid3X3 size={18} className="text-emerald-400" />
                <h3 className="text-sm font-medium text-slate-300">Bed Mesh</h3>
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={meshEnabled}
                  onChange={(e) => setBedMeshValue('enabled', e.target.checked)}
                  className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-emerald-500 focus:ring-emerald-500"
                />
                <span className="text-sm text-slate-400">Enable</span>
              </label>
            </div>

            {meshEnabled && (
              <div className="space-y-4">
                {/* Eddy Probe Info */}
                {isEddyProbe && (
                  <div className="bg-emerald-900/20 border border-emerald-700/50 rounded-lg p-3">
                    <div className="flex items-start gap-2">
                      <Info size={14} className="text-emerald-400 shrink-0 mt-0.5" />
                      <div className="text-xs text-emerald-300">
                        <strong>Eddy Probe Detected:</strong> You can use high probe counts (25x25 or 31x31)
                        for rapid mesh scanning with minimal time impact.
                      </div>
                    </div>
                  </div>
                )}

                {/* Mesh Bounds */}
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-2">
                    Mesh Bounds (mm)
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">Min X</label>
                      <input
                        type="number"
                        step="1"
                        value={meshMinX ?? ''}
                        onChange={(e) =>
                          setBedMeshValue('mesh_min_x', e.target.value ? parseInt(e.target.value) : undefined)
                        }
                        placeholder="5"
                        className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm placeholder-slate-500 focus:border-cyan-500"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">Min Y</label>
                      <input
                        type="number"
                        step="1"
                        value={meshMinY ?? ''}
                        onChange={(e) =>
                          setBedMeshValue('mesh_min_y', e.target.value ? parseInt(e.target.value) : undefined)
                        }
                        placeholder="5"
                        className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm placeholder-slate-500 focus:border-cyan-500"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">Max X</label>
                      <input
                        type="number"
                        step="1"
                        value={meshMaxX ?? ''}
                        onChange={(e) =>
                          setBedMeshValue('mesh_max_x', e.target.value ? parseInt(e.target.value) : undefined)
                        }
                        placeholder={bedSizeX ? String(bedSizeX - 5) : '295'}
                        className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm placeholder-slate-500 focus:border-cyan-500"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">Max Y</label>
                      <input
                        type="number"
                        step="1"
                        value={meshMaxY ?? ''}
                        onChange={(e) =>
                          setBedMeshValue('mesh_max_y', e.target.value ? parseInt(e.target.value) : undefined)
                        }
                        placeholder={bedSizeY ? String(bedSizeY - 5) : '295'}
                        className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm placeholder-slate-500 focus:border-cyan-500"
                      />
                    </div>
                  </div>
                  {bedSizeX && bedSizeY && (
                    <p className="text-xs text-slate-500 mt-2">
                      Bed size: {bedSizeX}x{bedSizeY}mm
                      {probeXOffset !== 0 || probeYOffset !== 0 ? (
                        <> — Probe offset: X={probeXOffset}, Y={probeYOffset}</>
                      ) : null}
                    </p>
                  )}
                </div>

                {/* Probe Count */}
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">
                    Probe Count (X, Y)
                  </label>
                  <input
                    type="text"
                    value={probeCount}
                    onChange={(e) => setBedMeshValue('probe_count', e.target.value || undefined)}
                    placeholder={isEddyProbe ? '25,25' : '5,5'}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm placeholder-slate-500 focus:border-cyan-500"
                  />
                  <p className="text-xs text-slate-500 mt-1">
                    {isEddyProbe
                      ? 'Eddy probes: 25,25 or 31,31 for rapid scan. Traditional probes: 5,5 or 7,7.'
                      : 'Format: X,Y (e.g., 5,5). More points = better mesh but slower.'}
                  </p>
                </div>

                {/* Quick Presets */}
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-2">
                    Quick Presets
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() => setBedMeshValue('probe_count', '5,5')}
                      className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                        probeCount === '5,5'
                          ? 'bg-emerald-600 text-white'
                          : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                      }`}
                    >
                      5x5 (Fast)
                    </button>
                    <button
                      onClick={() => setBedMeshValue('probe_count', '7,7')}
                      className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                        probeCount === '7,7'
                          ? 'bg-emerald-600 text-white'
                          : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                      }`}
                    >
                      7x7
                    </button>
                    {isEddyProbe && (
                      <>
                        <button
                          onClick={() => setBedMeshValue('probe_count', '25,25')}
                          className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                            probeCount === '25,25'
                              ? 'bg-emerald-600 text-white'
                              : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                          }`}
                        >
                          25x25 (Eddy)
                        </button>
                        <button
                          onClick={() => setBedMeshValue('probe_count', '31,31')}
                          className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                            probeCount === '31,31'
                              ? 'bg-emerald-600 text-white'
                              : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                          }`}
                        >
                          31x31 (Eddy)
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {/* Mesh Algorithm */}
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">
                    Interpolation Algorithm
                  </label>
                  <select
                    value={getBedMeshValue('algorithm', 'bicubic')}
                    onChange={(e) => setBedMeshValue('algorithm', e.target.value)}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-cyan-500"
                  >
                    <option value="lagrange">Lagrange (for small meshes, &lt;6x6)</option>
                    <option value="bicubic">Bicubic (recommended for 6x6+)</option>
                  </select>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Z Tilt Points Info */}
        {selectedType === 'z_tilt' && hasProbe && (
          <div className="border-t border-slate-700 pt-4">
            <h3 className="text-sm font-medium text-slate-300 mb-3">Z Tilt Configuration</h3>
            <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700">
              <p className="text-xs text-slate-400">
                Z tilt probe points will be auto-configured based on your bed size and Z motor positions.
                For fine-tuning, edit the generated config file.
              </p>
            </div>
          </div>
        )}

        {/* QGL Points Info */}
        {selectedType === 'qgl' && hasProbe && (
          <div className="border-t border-slate-700 pt-4">
            <h3 className="text-sm font-medium text-slate-300 mb-3">Quad Gantry Level Configuration</h3>
            <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700">
              <p className="text-xs text-slate-400">
                QGL probe points will be auto-configured for the four corners based on your bed size.
                For fine-tuning, edit the generated config file.
              </p>
            </div>
          </div>
        )}
      </div>
    </ConfigPanel>
  );
}
