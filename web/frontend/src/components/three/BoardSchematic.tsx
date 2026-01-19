import { useRef, useState, useMemo } from 'react';
import { Html } from '@react-three/drei';
import * as THREE from 'three';
import useWizardStore from '../../stores/wizardStore';

// Board data structure (matches API response)
interface BoardData {
  id: string;
  name: string;
  manufacturer: string;
  mcu?: string;
  motor_ports?: Record<string, MotorPort>;
  fan_ports?: Record<string, SimplePort>;
  heater_ports?: Record<string, SimplePort>;
  thermistor_ports?: Record<string, SimplePort>;
  endstop_ports?: Record<string, SimplePort>;
  probe_ports?: Record<string, ProbePort>;
  misc_ports?: Record<string, any>;
}

interface MotorPort {
  label: string;
  step_pin: string;
  dir_pin: string;
  enable_pin: string;
  uart_pin?: string;
  cs_pin?: string;
  diag_pin?: string;
}

interface SimplePort {
  label: string;
  pin: string;
}

interface ProbePort {
  label: string;
  signal_pin?: string;
  servo_pin?: string;
  pin?: string;
}

interface BoardSchematicProps {
  position: [number, number, number];
  boardData: BoardData | null | undefined;
  onPortClick?: (portType: string, portId: string, portData: any) => void;
  scale?: number;
}

interface ConnectorProps {
  id: string;
  label: string;
  type: 'motor' | 'fan' | 'heater' | 'thermistor' | 'endstop' | 'probe' | 'misc';
  portData: any;
  isAssigned: boolean;
  assignedTo?: string;
  isHighlighted: boolean;
  onClick: () => void;
}

// Color scheme for different port types
const PORT_COLORS = {
  motor: { bg: '#1e3a5f', border: '#3b82f6', hover: '#60a5fa' },
  fan: { bg: '#1e3a3a', border: '#14b8a6', hover: '#5eead4' },
  heater: { bg: '#3f1e1e', border: '#ef4444', hover: '#f87171' },
  thermistor: { bg: '#3f2e1e', border: '#f59e0b', hover: '#fbbf24' },
  endstop: { bg: '#2e1e3f', border: '#a855f7', hover: '#c084fc' },
  probe: { bg: '#1e2e3f', border: '#6366f1', hover: '#818cf8' },
  misc: { bg: '#2e2e2e', border: '#6b7280', hover: '#9ca3af' },
};

function Connector({ id, label, type, portData, isAssigned, assignedTo, isHighlighted, onClick }: ConnectorProps) {
  const [hovered, setHovered] = useState(false);
  const colors = PORT_COLORS[type];
  
  const bgColor = isAssigned ? '#065f46' : isHighlighted ? colors.hover : hovered ? colors.border : colors.bg;
  const borderColor = isAssigned ? '#10b981' : isHighlighted ? '#ffffff' : colors.border;
  
  // Get pin info for tooltip
  const pinInfo = useMemo(() => {
    if (!portData) return '';
    if (portData.step_pin) {
      return `Step: ${portData.step_pin}, Dir: ${portData.dir_pin}`;
    }
    if (portData.pin) {
      return `Pin: ${portData.pin}`;
    }
    if (portData.signal_pin) {
      return `Signal: ${portData.signal_pin}${portData.servo_pin ? `, Servo: ${portData.servo_pin}` : ''}`;
    }
    return '';
  }, [portData]);

  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="relative flex flex-col items-center justify-center transition-all duration-150"
      style={{
        backgroundColor: bgColor,
        border: `2px solid ${borderColor}`,
        borderRadius: '4px',
        padding: '4px 6px',
        minWidth: '50px',
        cursor: 'pointer',
      }}
      title={pinInfo}
    >
      <span className="text-[9px] font-bold text-white truncate max-w-[45px]">
        {id}
      </span>
      {isAssigned && assignedTo && (
        <span className="text-[7px] text-emerald-300 truncate max-w-[45px]">
          {assignedTo}
        </span>
      )}
      {(hovered || isHighlighted) && !isAssigned && (
        <span className="text-[7px] text-slate-300 truncate max-w-[45px]">
          {label}
        </span>
      )}
    </button>
  );
}

function ConnectorRow({ 
  title, 
  ports, 
  type, 
  assignedPorts, 
  highlightType,
  onPortClick 
}: { 
  title: string;
  ports: Record<string, any>;
  type: ConnectorProps['type'];
  assignedPorts: Map<string, string>;
  highlightType: string | null;
  onPortClick: (portId: string, portData: any) => void;
}) {
  if (!ports || Object.keys(ports).length === 0) return null;

  const isHighlighted = highlightType === type;

  return (
    <div className="flex flex-col gap-1">
      <div className="text-[8px] font-semibold text-slate-400 uppercase tracking-wider">
        {title}
      </div>
      <div className="flex flex-wrap gap-1">
        {Object.entries(ports).map(([portId, portData]) => (
          <Connector
            key={portId}
            id={portId}
            label={(portData as any).label || portId}
            type={type}
            portData={portData}
            isAssigned={assignedPorts.has(portId)}
            assignedTo={assignedPorts.get(portId)}
            isHighlighted={isHighlighted}
            onClick={() => onPortClick(portId, portData)}
          />
        ))}
      </div>
    </div>
  );
}

export function BoardSchematic({ position, boardData, onPortClick, scale = 1 }: BoardSchematicProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const state = useWizardStore((state) => state.state);
  const activePanel = useWizardStore((state) => state.activePanel);

  // Determine which port type to highlight based on active panel
  const highlightType = useMemo(() => {
    if (!activePanel) return null;
    if (activePanel.startsWith('stepper_')) return 'motor';
    if (activePanel === 'fans' || activePanel.includes('fan')) return 'fan';
    if (activePanel === 'heater_bed' || activePanel === 'hotend') return 'heater';
    if (activePanel === 'probe') return 'probe';
    if (activePanel.includes('thermistor')) return 'thermistor';
    return null;
  }, [activePanel]);

  // Build map of assigned ports
  const assignedPorts = useMemo(() => {
    const map = new Map<string, string>();
    
    // Check stepper motor ports
    const stepperPrefixes = ['stepper_x', 'stepper_y', 'stepper_z', 'stepper_z1', 'stepper_z2', 'stepper_z3', 'stepper_x1', 'stepper_y1', 'extruder'];
    stepperPrefixes.forEach(prefix => {
      const port = state[`${prefix}.motor_port`];
      if (port) {
        map.set(port, prefix.replace('stepper_', '').toUpperCase());
      }
    });

    // Check fan ports
    ['fans.part_cooling', 'fans.hotend', 'fans.controller', 'fans.exhaust'].forEach(key => {
      const port = state[`${key}.port`];
      if (port) {
        const name = key.split('.')[1];
        map.set(port, name);
      }
    });

    // Check heater ports
    if (state['heater_bed.heater_port']) {
      map.set(state['heater_bed.heater_port'], 'BED');
    }
    if (state['hotend.heater_port']) {
      map.set(state['hotend.heater_port'], 'HE');
    }

    // Check thermistor ports
    if (state['heater_bed.thermistor_port']) {
      map.set(state['heater_bed.thermistor_port'], 'T-BED');
    }
    if (state['hotend.thermistor_port']) {
      map.set(state['hotend.thermistor_port'], 'T-HE');
    }

    // Check endstop ports
    stepperPrefixes.forEach(prefix => {
      const port = state[`${prefix}.endstop_port`];
      if (port) {
        map.set(port, prefix.replace('stepper_', '').toUpperCase() + '-ES');
      }
    });

    return map;
  }, [state]);

  const handlePortClick = (portType: string, portId: string, portData: any) => {
    if (onPortClick) {
      onPortClick(portType, portId, portData);
    }
  };

  if (!boardData) {
    return (
      <group position={position}>
        <mesh>
          <boxGeometry args={[0.15, 0.12, 0.02]} />
          <meshStandardMaterial color="#1f2937" />
        </mesh>
        <Html center>
          <div className="text-slate-500 text-xs whitespace-nowrap">
            Select a board
          </div>
        </Html>
      </group>
    );
  }

  return (
    <group position={position}>
      {/* Board backing */}
      <mesh ref={meshRef}>
        <boxGeometry args={[0.32 * scale, 0.26 * scale, 0.01]} />
        <meshStandardMaterial color="#0c1222" metalness={0.1} roughness={0.8} />
      </mesh>

      {/* Board schematic overlay */}
      <Html
        center
        transform
        distanceFactor={1.2}
        style={{
          width: `${280 * scale}px`,
          pointerEvents: 'auto',
        }}
      >
        <div 
          className="bg-slate-900/95 border border-slate-700 rounded-lg p-2 shadow-xl"
          style={{ 
            fontSize: `${10 * scale}px`,
          }}
        >
          {/* Board title */}
          <div className="text-center mb-2 pb-1 border-b border-slate-700">
            <div className="text-[10px] font-bold text-cyan-400">
              {boardData.name}
            </div>
            <div className="text-[7px] text-slate-500">
              {boardData.manufacturer}
            </div>
          </div>

          {/* Connector groups */}
          <div className="space-y-2">
            <ConnectorRow
              title="Motors"
              ports={boardData.motor_ports || {}}
              type="motor"
              assignedPorts={assignedPorts}
              highlightType={highlightType}
              onPortClick={(id, data) => handlePortClick('motor', id, data)}
            />

            <div className="flex gap-3">
              <ConnectorRow
                title="Heaters"
                ports={boardData.heater_ports || {}}
                type="heater"
                assignedPorts={assignedPorts}
                highlightType={highlightType}
                onPortClick={(id, data) => handlePortClick('heater', id, data)}
              />
              <ConnectorRow
                title="Fans"
                ports={boardData.fan_ports || {}}
                type="fan"
                assignedPorts={assignedPorts}
                highlightType={highlightType}
                onPortClick={(id, data) => handlePortClick('fan', id, data)}
              />
            </div>

            <div className="flex gap-3">
              <ConnectorRow
                title="Temps"
                ports={boardData.thermistor_ports || {}}
                type="thermistor"
                assignedPorts={assignedPorts}
                highlightType={highlightType}
                onPortClick={(id, data) => handlePortClick('thermistor', id, data)}
              />
              <ConnectorRow
                title="Endstops"
                ports={boardData.endstop_ports || {}}
                type="endstop"
                assignedPorts={assignedPorts}
                highlightType={highlightType}
                onPortClick={(id, data) => handlePortClick('endstop', id, data)}
              />
            </div>

            {boardData.probe_ports && Object.keys(boardData.probe_ports).length > 0 && (
              <ConnectorRow
                title="Probe"
                ports={boardData.probe_ports}
                type="probe"
                assignedPorts={assignedPorts}
                highlightType={highlightType}
                onPortClick={(id, data) => handlePortClick('probe', id, data)}
              />
            )}

            {boardData.misc_ports && Object.keys(boardData.misc_ports).length > 0 && (
              <ConnectorRow
                title="Other"
                ports={boardData.misc_ports}
                type="misc"
                assignedPorts={assignedPorts}
                highlightType={highlightType}
                onPortClick={(id, data) => handlePortClick('misc', id, data)}
              />
            )}
          </div>
        </div>
      </Html>
    </group>
  );
}

export default BoardSchematic;
