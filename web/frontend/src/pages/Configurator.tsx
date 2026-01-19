import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { PrinterScene } from '../components/three/PrinterScene';
import useWizardStore from '../stores/wizardStore';
import { stateApi } from '../services/api';
import {
  MCUPanel,
  ToolboardPanel,
  StepperPanel,
  ExtruderPanel,
  HotendPanel,
  HeaterBedPanel,
  ProbePanel,
  FanPanel,
  ZConfigPanel,
  ToolingPanel,
  HomingPanel,
  BedLevelingPanel,
} from '../components/panels';
import { MacrosPanel } from '../components/panels/MacrosPanel';
import { ConfigPreview } from '../components/preview/ConfigPreview';
import {
  Cpu,
  CircuitBoard,
  Settings,
  Flame,
  Thermometer,
  Crosshair,
  Fan,
  ChevronLeft,
  Download,
  RotateCcw,
  Save,
  Upload,
  Menu,
  X,
  ArrowDown,
  Wrench,
  Loader2,
  Check,
  AlertCircle,
  Home,
  Layers,
  Play,
} from 'lucide-react';

interface SidebarItem {
  id: string;
  name: string;
  icon: typeof Cpu;
  color: string;
  section?: string;
}

// Base sidebar items (always shown)
const BASE_SIDEBAR_ITEMS: SidebarItem[] = [
  // Core Components
  { id: 'mcu', name: 'Mainboard', icon: Cpu, color: 'text-cyan-400', section: 'Core' },
  { id: 'toolboard', name: 'Toolboard', icon: CircuitBoard, color: 'text-emerald-400', section: 'Core' },
  { id: 'z_config', name: 'Z Config', icon: ArrowDown, color: 'text-indigo-400', section: 'Core' },
  { id: 'tooling', name: 'Tooling', icon: Wrench, color: 'text-amber-400', section: 'Core' },

  // Heating
  { id: 'extruder', name: 'Extruder', icon: Settings, color: 'text-purple-400', section: 'Heating' },
  { id: 'hotend', name: 'Hotend', icon: Flame, color: 'text-orange-400', section: 'Heating' },
  { id: 'heater_bed', name: 'Heated Bed', icon: Thermometer, color: 'text-red-400', section: 'Heating' },

  // Sensors & Leveling
  { id: 'probe', name: 'Probe', icon: Crosshair, color: 'text-violet-400', section: 'Leveling' },
  { id: 'homing', name: 'Homing', icon: Home, color: 'text-indigo-400', section: 'Leveling' },
  { id: 'bed_leveling', name: 'Bed Leveling', icon: Layers, color: 'text-teal-400', section: 'Leveling' },

  // Cooling
  { id: 'fans', name: 'Fans', icon: Fan, color: 'text-sky-400', section: 'Cooling' },

  // Workflow
  { id: 'macros', name: 'Macros', icon: Play, color: 'text-purple-400', section: 'Workflow' },
];

// Build sidebar items based on kinematics
function getSidebarItems(kinematics: string): SidebarItem[] {
  const isAWD = kinematics === 'hybrid_corexy';
  
  // Motion items depend on kinematics
  const motionItems: SidebarItem[] = [
    { id: 'stepper_x', name: 'Stepper X', icon: Settings, color: 'text-blue-400', section: 'Motion' },
    { id: 'stepper_y', name: 'Stepper Y', icon: Settings, color: 'text-blue-400', section: 'Motion' },
  ];
  
  // Add X1 and Y1 for AWD
  if (isAWD) {
    motionItems.push(
      { id: 'stepper_x1', name: 'Stepper X1', icon: Settings, color: 'text-blue-400', section: 'Motion' },
      { id: 'stepper_y1', name: 'Stepper Y1', icon: Settings, color: 'text-blue-400', section: 'Motion' },
    );
  }
  
  motionItems.push(
    { id: 'stepper_z', name: 'Stepper Z', icon: Settings, color: 'text-blue-400', section: 'Motion' },
  );
  
  // Insert motion items after Core section
  const coreItems = BASE_SIDEBAR_ITEMS.filter(item => item.section === 'Core');
  const otherItems = BASE_SIDEBAR_ITEMS.filter(item => item.section !== 'Core');
  
  return [...coreItems, ...motionItems, ...otherItems];
}

export function Configurator() {
  const navigate = useNavigate();
  const kinematics = useWizardStore((state) => state.state['printer.kinematics'] || '');
  const modelType = useWizardStore((state) => state.state['printer.model'] || '');
  const activePanel = useWizardStore((state) => state.activePanel);
  const setActivePanel = useWizardStore((state) => state.setActivePanel);
  const resetState = useWizardStore((state) => state.resetState);

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [previewOpen, setPreviewOpen] = useState(true);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');
  const [statusMessage, setStatusMessage] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const wizardState = useWizardStore((state) => state.state);
  const loadState = useWizardStore((state) => state.loadState);

  if (!kinematics) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-slate-900 text-white">
        <div className="text-6xl mb-4">🔧</div>
        <h2 className="text-2xl font-bold mb-2">No Kinematics Selected</h2>
        <p className="text-slate-400 mb-6">Please select your printer type to continue.</p>
        <button
          onClick={() => navigate('/select-kinematics')}
          className="px-6 py-3 bg-cyan-600 hover:bg-cyan-500 rounded-lg font-medium transition-colors"
        >
          Select Kinematics
        </button>
      </div>
    );
  }

  const renderActivePanel = () => {
    if (!activePanel) return null;

    // Z Configuration panel
    if (activePanel === 'z_config') {
      return <ZConfigPanel />;
    }

    // Tooling panel
    if (activePanel === 'tooling') {
      return <ToolingPanel />;
    }

    // MCU panel
    if (activePanel === 'mcu') {
      return <MCUPanel />;
    }

    // Toolboard panel
    if (activePanel === 'toolboard') {
      return <ToolboardPanel />;
    }

    // Stepper panels (including dynamic Z steppers)
    if (activePanel.startsWith('stepper_')) {
      return <StepperPanel stepperName={activePanel} />;
    }

    // Extruder panel (cold end - motor/gears)
    if (activePanel === 'extruder' || activePanel.startsWith('extruder')) {
      return <ExtruderPanel />;
    }

    // Hotend panel (hot end - heater/thermistor)
    if (activePanel === 'hotend') {
      return <HotendPanel />;
    }

    // Other panels
    switch (activePanel) {
      case 'heater_bed':
        return <HeaterBedPanel />;
      case 'probe':
        return <ProbePanel />;
      case 'homing':
        return <HomingPanel />;
      case 'bed_leveling':
        return <BedLevelingPanel />;
      case 'fans':
        return <FanPanel />;
      case 'macros':
        return <MacrosPanel />;
      default:
        return null;
    }
  };

  const handleReset = () => {
    if (window.confirm('Reset all configuration? This cannot be undone.')) {
      resetState();
      navigate('/select-kinematics');
    }
  };

  // Save state to server (creates .gschpoozi_state.json)
  const handleSaveState = async () => {
    setSaveStatus('saving');
    setStatusMessage('');
    try {
      const result = await stateApi.save(wizardState);
      if (result.success) {
        setSaveStatus('success');
        setStatusMessage(`Saved to ${result.path}`);
        setTimeout(() => setSaveStatus('idle'), 3000);
      } else {
        throw new Error(result.message || 'Save failed');
      }
    } catch (err) {
      setSaveStatus('error');
      setStatusMessage(err instanceof Error ? err.message : 'Save failed');
      setTimeout(() => setSaveStatus('idle'), 5000);
    }
  };

  // Export state as downloadable JSON file
  const handleExportState = () => {
    // Build the same format as CLI wizard expects
    const exportData = {
      wizard: {
        version: '3.0',
        created: new Date().toISOString(),
        last_modified: new Date().toISOString(),
      },
      config: {} as Record<string, any>,
    };

    // Convert flat dot-notation to nested structure
    for (const [key, value] of Object.entries(wizardState)) {
      if (value === undefined || value === null || value === '') continue;
      const parts = key.split('.');
      let current = exportData.config;
      for (let i = 0; i < parts.length - 1; i++) {
        if (!current[parts[i]]) current[parts[i]] = {};
        current = current[parts[i]];
      }
      current[parts[parts.length - 1]] = value;
    }

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = '.gschpoozi_state.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    setSaveStatus('success');
    setStatusMessage('State exported! Place in ~/printer_data/config/ to use with CLI wizard.');
    setTimeout(() => setSaveStatus('idle'), 5000);
  };

  // Import state from JSON file
  const handleImportState = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = JSON.parse(e.target?.result as string);
        
        // Handle both flat and nested formats
        let flatState: Record<string, any> = {};
        
        if (data.config) {
          // Nested format from CLI wizard - flatten it
          const flatten = (obj: Record<string, any>, prefix = '') => {
            for (const [key, value] of Object.entries(obj)) {
              const fullKey = prefix ? `${prefix}.${key}` : key;
              if (value && typeof value === 'object' && !Array.isArray(value)) {
                flatten(value, fullKey);
              } else {
                flatState[fullKey] = value;
              }
            }
          };
          flatten(data.config);
        } else {
          // Already flat format
          flatState = data;
        }

        loadState(flatState);
        setSaveStatus('success');
        setStatusMessage('State imported successfully!');
        setTimeout(() => setSaveStatus('idle'), 3000);
      } catch (err) {
        setSaveStatus('error');
        setStatusMessage('Invalid state file format');
        setTimeout(() => setSaveStatus('idle'), 5000);
      }
    };
    reader.readAsText(file);
    
    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Get dynamic sidebar items based on kinematics
  const sidebarItems = getSidebarItems(kinematics);
  
  // Group sidebar items by section
  const sections = sidebarItems.reduce((acc, item) => {
    const section = item.section || 'Other';
    if (!acc[section]) acc[section] = [];
    acc[section].push(item);
    return acc;
  }, {} as Record<string, SidebarItem[]>);

  return (
    <div className="flex h-screen bg-slate-900 text-white overflow-hidden">
      {/* Left Sidebar */}
      <div
        className={`${
          sidebarOpen ? 'w-64' : 'w-16'
        } bg-slate-800 border-r border-slate-700 flex flex-col transition-all duration-300`}
      >
        {/* Header */}
        <div className="p-4 border-b border-slate-700 flex items-center justify-between">
          {sidebarOpen && (
            <div>
              <h1 className="font-bold text-lg text-cyan-400">gschpoozi</h1>
              <p className="text-xs text-slate-500 capitalize">{kinematics.replace('_', ' ')}</p>
            </div>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
          >
            {sidebarOpen ? <ChevronLeft size={18} /> : <Menu size={18} />}
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-2 overflow-y-auto">
          {Object.entries(sections).map(([sectionName, items]) => (
            <div key={sectionName} className="mb-4">
              {sidebarOpen && (
                <div className="px-3 py-1 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  {sectionName}
                </div>
              )}
              {items.map((item) => {
                const Icon = item.icon;
                const isActive = activePanel === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setActivePanel(isActive ? null : item.id)}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg mb-1 transition-colors ${
                      isActive
                        ? 'bg-slate-700 text-white'
                        : 'text-slate-400 hover:bg-slate-700/50 hover:text-white'
                    }`}
                  >
                    <Icon size={18} className={isActive ? item.color : ''} />
                    {sidebarOpen && <span className="text-sm">{item.name}</span>}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        {/* Actions */}
        <div className="p-2 border-t border-slate-700">
          {/* Hidden file input for import */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            onChange={handleImportState}
            className="hidden"
          />

          {/* Status message */}
          {saveStatus !== 'idle' && sidebarOpen && (
            <div className={`mb-2 px-3 py-2 rounded-lg text-xs flex items-center gap-2 ${
              saveStatus === 'saving' ? 'bg-blue-900/30 text-blue-300' :
              saveStatus === 'success' ? 'bg-emerald-900/30 text-emerald-300' :
              'bg-red-900/30 text-red-300'
            }`}>
              {saveStatus === 'saving' && <Loader2 size={12} className="animate-spin" />}
              {saveStatus === 'success' && <Check size={12} />}
              {saveStatus === 'error' && <AlertCircle size={12} />}
              <span className="truncate">{statusMessage || (saveStatus === 'saving' ? 'Saving...' : '')}</span>
            </div>
          )}

          {sidebarOpen ? (
            <div className="space-y-1">
              <button
                onClick={handleSaveState}
                disabled={saveStatus === 'saving'}
                className="w-full flex items-center gap-3 px-3 py-2 text-sm text-slate-400 hover:bg-slate-700/50 hover:text-white rounded-lg transition-colors disabled:opacity-50"
              >
                {saveStatus === 'saving' ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                Save State
              </button>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="w-full flex items-center gap-3 px-3 py-2 text-sm text-slate-400 hover:bg-slate-700/50 hover:text-white rounded-lg transition-colors"
              >
                <Upload size={16} />
                Import State
              </button>
              <button
                onClick={handleExportState}
                className="w-full flex items-center gap-3 px-3 py-2 text-sm text-slate-400 hover:bg-slate-700/50 hover:text-white rounded-lg transition-colors"
              >
                <Download size={16} />
                Export State
              </button>
              <button
                onClick={handleReset}
                className="w-full flex items-center gap-3 px-3 py-2 text-sm text-red-400 hover:bg-red-900/20 hover:text-red-300 rounded-lg transition-colors"
              >
                <RotateCcw size={16} />
                Reset
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-1">
              <button
                onClick={handleSaveState}
                disabled={saveStatus === 'saving'}
                title="Save State"
                className="p-2 text-slate-400 hover:bg-slate-700/50 hover:text-white rounded-lg disabled:opacity-50"
              >
                {saveStatus === 'saving' ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              </button>
              <button
                onClick={() => fileInputRef.current?.click()}
                title="Import State"
                className="p-2 text-slate-400 hover:bg-slate-700/50 hover:text-white rounded-lg"
              >
                <Upload size={16} />
              </button>
              <button
                onClick={handleExportState}
                title="Export State"
                className="p-2 text-slate-400 hover:bg-slate-700/50 hover:text-white rounded-lg"
              >
                <Download size={16} />
              </button>
              <button
                onClick={handleReset}
                title="Reset"
                className="p-2 text-red-400 hover:bg-red-900/20 hover:text-red-300 rounded-lg"
              >
                <RotateCcw size={16} />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col">
        {/* Top Bar */}
        <div className="h-12 bg-slate-800/50 border-b border-slate-700 flex items-center justify-between px-4">
          <div className="flex items-center gap-4">
            <span className="text-sm text-slate-400">
              Click components in the 3D view or use the sidebar to configure
            </span>
          </div>
          <button
            onClick={() => setPreviewOpen(!previewOpen)}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-slate-400 hover:text-white bg-slate-700/50 hover:bg-slate-700 rounded-lg transition-colors"
          >
            {previewOpen ? <X size={14} /> : <Menu size={14} />}
            Preview
          </button>
        </div>

        {/* 3D Scene + Config Panel + Preview */}
        <div className="flex-1 flex overflow-hidden">
          {/* 3D Scene */}
          <div className="flex-1 relative bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
            <PrinterScene modelType={modelType} />

            {/* Active Panel Overlay */}
            {activePanel && renderActivePanel()}
          </div>

          {/* Config Preview */}
          {previewOpen && (
            <div className="w-[450px] border-l border-slate-700">
              <ConfigPreview />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
