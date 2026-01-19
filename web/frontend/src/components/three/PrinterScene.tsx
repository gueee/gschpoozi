import { useRef, useState, useEffect, useCallback, useMemo } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import type { ThreeEvent } from '@react-three/fiber';
import { OrbitControls, Html, Grid, Environment, Float, RoundedBox } from '@react-three/drei';
import * as THREE from 'three';
import useWizardStore from '../../stores/wizardStore';
import { StepperMotorModel, ExtruderModel, HotendModel, preloadModels } from './models';
import { BoardSchematic } from './BoardSchematic';
import { useBoard } from '../../hooks/useTemplates';

interface PrinterSceneProps {
  modelType: string;
}

// Shared component for hover/click effects (for non-model components)
function InteractiveComponent({
  position,
  size,
  name,
  label,
  color = '#64748b',
  hoverColor = '#06b6d4',
  selectedColor = '#0ea5e9',
  onClick,
  geometry = 'box',
  rotation,
}: {
  position: [number, number, number];
  size: [number, number, number] | number;
  name: string;
  label: string;
  color?: string;
  hoverColor?: string;
  selectedColor?: string;
  onClick: () => void;
  geometry?: 'box' | 'cylinder';
  rotation?: [number, number, number];
}) {
  const ref = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);
  const activePanel = useWizardStore((state) => state.activePanel);
  const isSelected = activePanel === name;

  useFrame(() => {
    if (ref.current) {
      const targetColor = isSelected ? selectedColor : hovered ? hoverColor : color;
      (ref.current.material as THREE.MeshStandardMaterial).color.lerp(
        new THREE.Color(targetColor),
        0.1
      );

      // Subtle pulse when selected
      if (isSelected) {
        ref.current.scale.setScalar(1 + Math.sin(Date.now() * 0.005) * 0.02);
      } else {
        ref.current.scale.lerp(new THREE.Vector3(1, 1, 1), 0.1);
      }
    }
  });

  const handlePointerOver = (e: ThreeEvent<PointerEvent>) => {
    e.stopPropagation();
    setHovered(true);
    document.body.style.cursor = 'pointer';
  };

  const handlePointerOut = () => {
    setHovered(false);
    document.body.style.cursor = 'default';
  };

  const handleClick = (e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    onClick();
  };

  return (
    <mesh
      ref={ref}
      position={position}
      rotation={rotation}
      onPointerOver={handlePointerOver}
      onPointerOut={handlePointerOut}
      onClick={handleClick}
    >
      {geometry === 'box' ? (
        <boxGeometry args={Array.isArray(size) ? size : [size, size, size]} />
      ) : (
        <cylinderGeometry args={[size as number * 0.5, size as number * 0.5, size as number, 32]} />
      )}
      <meshStandardMaterial color={color} metalness={0.3} roughness={0.7} />

      {/* Label */}
      {(hovered || isSelected) && (
        <Html
          position={[0, (Array.isArray(size) ? size[1] : size) * 0.7, 0]}
          center
          distanceFactor={4}
        >
          <div
            className={`px-2 py-1 rounded text-xs font-medium whitespace-nowrap transition-all ${
              isSelected
                ? 'bg-cyan-500 text-white'
                : 'bg-slate-800 text-white border border-slate-600'
            }`}
          >
            {label}
          </div>
        </Html>
      )}
    </mesh>
  );
}

// 2020 Extrusion profile component
function Extrusion2020({
  start,
  end,
  color = '#1e293b',
}: {
  start: [number, number, number];
  end: [number, number, number];
  color?: string;
}) {
  const length = Math.sqrt(
    Math.pow(end[0] - start[0], 2) +
    Math.pow(end[1] - start[1], 2) +
    Math.pow(end[2] - start[2], 2)
  );

  const midPoint: [number, number, number] = [
    (start[0] + end[0]) / 2,
    (start[1] + end[1]) / 2,
    (start[2] + end[2]) / 2,
  ];

  // Calculate rotation to align with direction
  const direction = new THREE.Vector3(
    end[0] - start[0],
    end[1] - start[1],
    end[2] - start[2]
  ).normalize();

  const quaternion = new THREE.Quaternion();
  quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction);
  const euler = new THREE.Euler().setFromQuaternion(quaternion);

  return (
    <group position={midPoint} rotation={[euler.x, euler.y, euler.z]}>
      <RoundedBox args={[0.02, length, 0.02]} radius={0.002} smoothness={2}>
        <meshStandardMaterial color={color} metalness={0.6} roughness={0.4} />
      </RoundedBox>
    </group>
  );
}

// Frame structure with 2020 extrusions
function PrinterFrame({ size }: { size: { x: number; y: number; z: number } }) {
  const frameColor = '#1e293b';

  // Corner positions
  const corners = {
    fbl: [-size.x / 2, 0, size.y / 2] as [number, number, number],         // front-bottom-left
    fbr: [size.x / 2, 0, size.y / 2] as [number, number, number],          // front-bottom-right
    bbl: [-size.x / 2, 0, -size.y / 2] as [number, number, number],        // back-bottom-left
    bbr: [size.x / 2, 0, -size.y / 2] as [number, number, number],         // back-bottom-right
    ftl: [-size.x / 2, size.z, size.y / 2] as [number, number, number],    // front-top-left
    ftr: [size.x / 2, size.z, size.y / 2] as [number, number, number],     // front-top-right
    btl: [-size.x / 2, size.z, -size.y / 2] as [number, number, number],   // back-top-left
    btr: [size.x / 2, size.z, -size.y / 2] as [number, number, number],    // back-top-right
  };

  return (
    <group>
      {/* Vertical posts */}
      <Extrusion2020 start={corners.fbl} end={corners.ftl} color={frameColor} />
      <Extrusion2020 start={corners.fbr} end={corners.ftr} color={frameColor} />
      <Extrusion2020 start={corners.bbl} end={corners.btl} color={frameColor} />
      <Extrusion2020 start={corners.bbr} end={corners.btr} color={frameColor} />

      {/* Top horizontal - front/back */}
      <Extrusion2020 start={corners.ftl} end={corners.ftr} color={frameColor} />
      <Extrusion2020 start={corners.btl} end={corners.btr} color={frameColor} />

      {/* Top horizontal - left/right */}
      <Extrusion2020 start={corners.ftl} end={corners.btl} color={frameColor} />
      <Extrusion2020 start={corners.ftr} end={corners.btr} color={frameColor} />

      {/* Bottom horizontal - front/back */}
      <Extrusion2020 start={corners.fbl} end={corners.fbr} color={frameColor} />
      <Extrusion2020 start={corners.bbl} end={corners.bbr} color={frameColor} />

      {/* Bottom horizontal - left/right */}
      <Extrusion2020 start={corners.fbl} end={corners.bbl} color={frameColor} />
      <Extrusion2020 start={corners.fbr} end={corners.bbr} color={frameColor} />
    </group>
  );
}

// Heated bed with texture
function PrintBed({
  size,
  onClick,
}: {
  size: { x: number; y: number };
  onClick: () => void;
}) {
  const ref = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);
  const activePanel = useWizardStore((state) => state.activePanel);
  const isSelected = activePanel === 'heater_bed';

  useFrame(() => {
    if (ref.current) {
      const targetColor = isSelected ? '#ef4444' : hovered ? '#dc2626' : '#334155';
      (ref.current.material as THREE.MeshStandardMaterial).color.lerp(
        new THREE.Color(targetColor),
        0.1
      );

      if (isSelected) {
        ref.current.scale.setScalar(1 + Math.sin(Date.now() * 0.005) * 0.01);
      } else {
        ref.current.scale.lerp(new THREE.Vector3(1, 1, 1), 0.1);
      }
    }
  });

  return (
    <group position={[0, 0.025, 0]}>
      {/* Main bed surface */}
      <mesh
        ref={ref}
        onPointerOver={(e) => { e.stopPropagation(); setHovered(true); document.body.style.cursor = 'pointer'; }}
        onPointerOut={() => { setHovered(false); document.body.style.cursor = 'default'; }}
        onClick={(e) => { e.stopPropagation(); onClick(); }}
      >
        <boxGeometry args={[size.x, 0.006, size.y]} />
        <meshStandardMaterial color="#334155" metalness={0.2} roughness={0.8} />
      </mesh>

      {/* Bed frame/heater underneath */}
      <mesh position={[0, -0.015, 0]}>
        <boxGeometry args={[size.x * 0.95, 0.02, size.y * 0.95]} />
        <meshStandardMaterial color="#1f2937" metalness={0.4} roughness={0.6} />
      </mesh>

      {/* Grid lines on bed surface */}
      <lineSegments position={[0, 0.004, 0]}>
        <edgesGeometry args={[new THREE.PlaneGeometry(size.x * 0.9, size.y * 0.9, 10, 10)]} />
        <lineBasicMaterial color="#475569" transparent opacity={0.3} />
      </lineSegments>

      {/* Label */}
      {(hovered || isSelected) && (
        <Html position={[0, 0.05, 0]} center distanceFactor={4}>
          <div
            className={`px-2 py-1 rounded text-xs font-medium whitespace-nowrap transition-all ${
              isSelected
                ? 'bg-red-500 text-white'
                : 'bg-slate-800 text-white border border-slate-600'
            }`}
          >
            Heated Bed
          </div>
        </Html>
      )}
    </group>
  );
}

// Toolhead assembly with separate Extruder and Hotend
function Toolhead({
  position,
  onExtruderClick,
  onHotendClick,
}: {
  position: [number, number, number];
  onExtruderClick: () => void;
  onHotendClick: () => void;
}) {
  return (
    <Float speed={2} rotationIntensity={0} floatIntensity={0.15}>
      <group position={position}>
        {/* Extruder (cold end) - top */}
        <ExtruderModel
          position={[0, 0.05, 0]}
          name="extruder"
          label="Extruder (Cold End)"
          onClick={onExtruderClick}
          color="#475569"
          hoverColor="#8b5cf6"
          selectedColor="#a78bfa"
        />

        {/* Hotend (hot end) - bottom */}
        <HotendModel
          position={[0, -0.01, 0]}
          name="hotend"
          label="Hotend"
          onClick={onHotendClick}
          color="#475569"
          hoverColor="#f97316"
          selectedColor="#fb923c"
        />

        {/* Mounting plate connecting them */}
        <mesh position={[0, 0.02, 0]}>
          <boxGeometry args={[0.06, 0.004, 0.04]} />
          <meshStandardMaterial color="#1f2937" metalness={0.5} roughness={0.5} />
        </mesh>
      </group>
    </Float>
  );
}

// Stepper motor using the new model component
function Stepper({
  position,
  name,
  label,
  onClick,
}: {
  position: [number, number, number];
  name: string;
  label: string;
  onClick: () => void;
}) {
  return (
    <StepperMotorModel
      position={position}
      name={name}
      label={label}
      onClick={onClick}
      color="#374151"
      hoverColor="#3b82f6"
      selectedColor="#60a5fa"
    />
  );
}

// MCU Board with interactive schematic
function MCUBoard({ 
  position, 
  boardData,
  onMcuClick,
  onPortClick 
}: { 
  position: [number, number, number]; 
  boardData: any;
  onMcuClick: () => void;
  onPortClick: (portType: string, portId: string, portData: any) => void;
}) {
  const activePanel = useWizardStore((state) => state.activePanel);
  
  // Determine if we should show expanded board view
  const shouldShowBoard = activePanel && (
    activePanel.startsWith('stepper_') ||
    activePanel === 'fans' ||
    activePanel === 'heater_bed' ||
    activePanel === 'hotend' ||
    activePanel === 'probe' ||
    activePanel === 'extruder'
  );

  if (shouldShowBoard && boardData) {
    // Show expanded board schematic
    return (
      <BoardSchematic
        position={position}
        boardData={boardData}
        onPortClick={onPortClick}
        scale={1.2}
      />
    );
  }

  // Show simple MCU representation when not in port-assignment mode
  return (
    <group position={position}>
      {/* Board - upright against back wall */}
      <InteractiveComponent
        position={[0, 0, 0]}
        size={[0.15, 0.12, 0.02]}
        name="mcu"
        label="MCU / Mainboard"
        color="#065f46"
        hoverColor="#10b981"
        selectedColor="#34d399"
        onClick={onMcuClick}
      />
      {/* USB port indicator */}
      <mesh position={[-0.05, -0.04, 0.015]}>
        <boxGeometry args={[0.02, 0.01, 0.01]} />
        <meshStandardMaterial color="#1f2937" />
      </mesh>
      {/* Processor heatsink */}
      <mesh position={[0.03, 0.02, 0.015]}>
        <boxGeometry args={[0.025, 0.025, 0.015]} />
        <meshStandardMaterial color="#374151" metalness={0.6} roughness={0.4} />
      </mesh>
      {/* Driver heatsinks */}
      {[-0.04, -0.02, 0, 0.02, 0.04].map((x, i) => (
        <mesh key={i} position={[x, -0.02, 0.012]}>
          <boxGeometry args={[0.012, 0.012, 0.008]} />
          <meshStandardMaterial color="#1f2937" metalness={0.5} roughness={0.5} />
        </mesh>
      ))}
      
      {/* Board name label if available */}
      {boardData && (
        <Html position={[0, 0.08, 0.02]} center distanceFactor={4}>
          <div className="text-[8px] text-cyan-400 bg-slate-900/80 px-1 rounded whitespace-nowrap">
            {boardData.name}
          </div>
        </Html>
      )}
    </group>
  );
}

// Camera controller for smooth transitions
function CameraController({ targetPosition, enabled }: { targetPosition: THREE.Vector3 | null; enabled: boolean }) {
  const { camera } = useThree();
  const defaultPosition = useRef(new THREE.Vector3(2, 1.5, 2));
  
  useFrame(() => {
    if (!enabled || !targetPosition) {
      // Lerp back to default position
      camera.position.lerp(defaultPosition.current, 0.02);
    } else {
      // Lerp to target position
      camera.position.lerp(targetPosition, 0.05);
    }
  });
  
  return null;
}

// Dynamic Z-motors based on count from state
function ZMotors({
  size,
  zMotorCount,
  onClick
}: {
  size: { x: number; y: number; z: number };
  zMotorCount: number;
  onClick: (name: string) => void;
}) {
  const getZMotorPositions = () => {
    const offset = 0.1;
    const positions: { pos: [number, number, number]; name: string; label: string }[] = [];

    switch (zMotorCount) {
      case 1:
        positions.push({
          pos: [0, offset, -size.y / 2 + offset],
          name: 'stepper_z',
          label: 'Z Stepper'
        });
        break;
      case 2:
        positions.push({
          pos: [-size.x / 2 + offset, offset, -size.y / 2 + offset],
          name: 'stepper_z',
          label: 'Z Stepper (Left)'
        });
        positions.push({
          pos: [size.x / 2 - offset, offset, -size.y / 2 + offset],
          name: 'stepper_z1',
          label: 'Z1 Stepper (Right)'
        });
        break;
      case 3:
        positions.push({
          pos: [-size.x / 2 + offset, offset, -size.y / 2 + offset],
          name: 'stepper_z',
          label: 'Z Stepper (Rear Left)'
        });
        positions.push({
          pos: [size.x / 2 - offset, offset, -size.y / 2 + offset],
          name: 'stepper_z1',
          label: 'Z1 Stepper (Rear Right)'
        });
        positions.push({
          pos: [0, offset, size.y / 2 - offset],
          name: 'stepper_z2',
          label: 'Z2 Stepper (Front)'
        });
        break;
      case 4:
        positions.push({
          pos: [-size.x / 2 + offset, offset, -size.y / 2 + offset],
          name: 'stepper_z',
          label: 'Z Stepper (Rear Left)'
        });
        positions.push({
          pos: [size.x / 2 - offset, offset, -size.y / 2 + offset],
          name: 'stepper_z1',
          label: 'Z1 Stepper (Rear Right)'
        });
        positions.push({
          pos: [-size.x / 2 + offset, offset, size.y / 2 - offset],
          name: 'stepper_z2',
          label: 'Z2 Stepper (Front Left)'
        });
        positions.push({
          pos: [size.x / 2 - offset, offset, size.y / 2 - offset],
          name: 'stepper_z3',
          label: 'Z3 Stepper (Front Right)'
        });
        break;
      default:
        positions.push({
          pos: [0, offset, -size.y / 2 + offset],
          name: 'stepper_z',
          label: 'Z Stepper'
        });
    }

    return positions;
  };

  return (
    <>
      {getZMotorPositions().map(({ pos, name, label }) => (
        <Stepper
          key={name}
          position={pos}
          name={name}
          label={label}
          onClick={() => onClick(name)}
        />
      ))}
    </>
  );
}

// Main scene content
function SceneContent({ modelType }: { modelType: string }) {
  const setActivePanel = useWizardStore((state) => state.setActivePanel);
  const setField = useWizardStore((state) => state.setField);
  const activePanel = useWizardStore((state) => state.activePanel);
  const state = useWizardStore((state) => state.state);
  const zMotorCount = state['z_config.motor_count'] ?? 1;
  
  // Get board data for schematic
  const selectedBoard = state['mcu.main.board_type'];
  const { data: boardData } = useBoard(selectedBoard);

  // Preload models on mount
  useEffect(() => {
    preloadModels();
  }, []);

  const handleClick = (componentName: string) => {
    setActivePanel(componentName);
  };
  
  // Handle port click from board schematic
  const handlePortClick = useCallback((portType: string, portId: string, portData: any) => {
    // Determine which component to assign based on active panel
    if (!activePanel) return;
    
    let prefix = '';
    
    if (activePanel.startsWith('stepper_') && portType === 'motor') {
      prefix = activePanel;
      setField(`${prefix}.motor_port`, portId);
      // Auto-fill pins
      if (portData.step_pin) {
        setField(`${prefix}.step_pin`, portData.step_pin);
        setField(`${prefix}.dir_pin`, portData.dir_pin);
        setField(`${prefix}.enable_pin`, '!' + portData.enable_pin);
        if (portData.uart_pin) setField(`${prefix}.uart_pin`, portData.uart_pin);
        if (portData.cs_pin) setField(`${prefix}.cs_pin`, portData.cs_pin);
        if (portData.diag_pin) setField(`${prefix}.diag_pin`, portData.diag_pin);
      }
    } else if (activePanel === 'extruder' && portType === 'motor') {
      prefix = 'extruder';
      setField(`${prefix}.motor_port`, portId);
      if (portData.step_pin) {
        setField(`${prefix}.step_pin`, portData.step_pin);
        setField(`${prefix}.dir_pin`, portData.dir_pin);
        setField(`${prefix}.enable_pin`, '!' + portData.enable_pin);
        if (portData.uart_pin) setField(`${prefix}.uart_pin`, portData.uart_pin);
      }
    } else if (activePanel === 'heater_bed' && portType === 'heater') {
      setField('heater_bed.heater_port', portId);
      if (portData.pin) setField('heater_bed.heater_pin', portData.pin);
    } else if (activePanel === 'heater_bed' && portType === 'thermistor') {
      setField('heater_bed.thermistor_port', portId);
      if (portData.pin) setField('heater_bed.sensor_pin', portData.pin);
    } else if (activePanel === 'hotend' && portType === 'heater') {
      setField('hotend.heater_port', portId);
      if (portData.pin) setField('hotend.heater_pin', portData.pin);
    } else if (activePanel === 'hotend' && portType === 'thermistor') {
      setField('hotend.thermistor_port', portId);
      if (portData.pin) setField('hotend.sensor_pin', portData.pin);
    } else if (activePanel === 'fans' && portType === 'fan') {
      // For fans, we'd need to know which fan - for now assign to part cooling
      setField('fans.part_cooling.port', portId);
      if (portData.pin) setField('fans.part_cooling.pin', portData.pin);
    } else if (activePanel === 'probe' && portType === 'probe') {
      setField('probe.port', portId);
      if (portData.signal_pin) setField('probe.pin', portData.signal_pin);
      if (portData.servo_pin) setField('probe.servo_pin', portData.servo_pin);
    } else if (portType === 'endstop' && activePanel.startsWith('stepper_')) {
      prefix = activePanel;
      setField(`${prefix}.endstop_port`, portId);
      if (portData.pin) setField(`${prefix}.endstop_pin`, `^${portData.pin}`);
    }
  }, [activePanel, setField]);
  
  // Determine if camera should zoom to board
  const shouldZoomToBoard = activePanel && (
    activePanel.startsWith('stepper_') ||
    activePanel === 'fans' ||
    activePanel === 'heater_bed' ||
    activePanel === 'hotend' ||
    activePanel === 'probe' ||
    activePanel === 'extruder'
  );
  
  // Camera target position when zoomed to board
  const boardCameraPosition = useMemo(() => {
    return new THREE.Vector3(0, 0.5, 0.8);
  }, []);

  // Printer dimensions (scaled for visualization)
  const size = { x: 1.2, y: 1.2, z: 1.0 };

  const renderModel = () => {
    switch (modelType) {
      case 'voron': // CoreXY
        return (
          <group>
            <PrinterFrame size={size} />
            <PrintBed size={{ x: size.x * 0.8, y: size.y * 0.8 }} onClick={() => handleClick('heater_bed')} />
            <Toolhead
              position={[0, size.z * 0.6, 0]}
              onExtruderClick={() => handleClick('extruder')}
              onHotendClick={() => handleClick('hotend')}
            />

            {/* CoreXY Motors (rear corners) */}
            <Stepper position={[-size.x / 2 + 0.1, size.z - 0.1, -size.y / 2 + 0.1]} name="stepper_x" label="X Stepper (A belt)" onClick={() => handleClick('stepper_x')} />
            <Stepper position={[size.x / 2 - 0.1, size.z - 0.1, -size.y / 2 + 0.1]} name="stepper_y" label="Y Stepper (B belt)" onClick={() => handleClick('stepper_y')} />

            {/* Dynamic Z Motors */}
            <ZMotors size={size} zMotorCount={zMotorCount} onClick={handleClick} />

            {/* MCU Board - upright on back wall */}
            <MCUBoard 
              position={[0, size.z * 0.4, -size.y / 2 + 0.03]} 
              boardData={boardData}
              onMcuClick={() => handleClick('mcu')} 
              onPortClick={handlePortClick}
            />
          </group>
        );

      case 'ender': // Cartesian bed-slinger
        return (
          <group>
            <PrinterFrame size={size} />
            <PrintBed size={{ x: size.x * 0.8, y: size.y * 0.8 }} onClick={() => handleClick('heater_bed')} />
            <Toolhead
              position={[0, size.z * 0.5, 0]}
              onExtruderClick={() => handleClick('extruder')}
              onHotendClick={() => handleClick('hotend')}
            />

            {/* X Motor on gantry */}
            <Stepper position={[-size.x / 2 + 0.1, size.z * 0.5, 0]} name="stepper_x" label="X Stepper" onClick={() => handleClick('stepper_x')} />

            {/* Y Motor on bed */}
            <Stepper position={[0, 0.1, size.y / 2 - 0.1]} name="stepper_y" label="Y Stepper" onClick={() => handleClick('stepper_y')} />

            {/* Dynamic Z Motors */}
            <ZMotors size={size} zMotorCount={zMotorCount} onClick={handleClick} />

            {/* MCU Board - upright on back wall */}
            <MCUBoard 
              position={[0, size.z * 0.4, -size.y / 2 + 0.03]} 
              boardData={boardData}
              onMcuClick={() => handleClick('mcu')} 
              onPortClick={handlePortClick}
            />
          </group>
        );

      case 'kossel': // Delta
        const deltaRadius = 0.4;
        const towerHeight = size.z * 1.2;
        return (
          <group>
            {/* Circular bed */}
            <mesh position={[0, 0.025, 0]} onClick={() => handleClick('heater_bed')}>
              <cylinderGeometry args={[deltaRadius, deltaRadius, 0.05, 32]} />
              <meshStandardMaterial color="#334155" />
            </mesh>

            <Toolhead
              position={[0, size.z * 0.4, 0]}
              onExtruderClick={() => handleClick('extruder')}
              onHotendClick={() => handleClick('hotend')}
            />

            {/* Delta towers */}
            {[0, 120, 240].map((angle, i) => {
              const rad = (angle * Math.PI) / 180;
              const x = Math.sin(rad) * 0.6;
              const z = Math.cos(rad) * 0.6;
              const names = ['stepper_a', 'stepper_b', 'stepper_c'];
              const labels = ['A Tower', 'B Tower', 'C Tower'];
              return (
                <group key={angle}>
                  {/* Tower */}
                  <Extrusion2020
                    start={[x, 0, z]}
                    end={[x, towerHeight, z]}
                    color="#1e293b"
                  />
                  {/* Motor at bottom */}
                  <Stepper
                    position={[x, 0.1, z]}
                    name={names[i]}
                    label={labels[i]}
                    onClick={() => handleClick(names[i])}
                  />
                </group>
              );
            })}

            {/* MCU Board - upright on back */}
            <MCUBoard 
              position={[0, size.z * 0.3, -0.55]} 
              boardData={boardData}
              onMcuClick={() => handleClick('mcu')} 
              onPortClick={handlePortClick}
            />
          </group>
        );

      case 'vzbot': // Hybrid CoreXY (AWD)
        return (
          <group>
            <PrinterFrame size={size} />
            <PrintBed size={{ x: size.x * 0.8, y: size.y * 0.8 }} onClick={() => handleClick('heater_bed')} />
            <Toolhead
              position={[0, size.z * 0.6, 0]}
              onExtruderClick={() => handleClick('extruder')}
              onHotendClick={() => handleClick('hotend')}
            />

            {/* AWD: 4 XY motors - diagonal pairs */}
            <Stepper
              position={[-size.x / 2 + 0.1, size.z - 0.1, -size.y / 2 + 0.1]}
              name="stepper_x"
              label="X (A belt)"
              onClick={() => handleClick('stepper_x')}
            />
            <Stepper
              position={[size.x / 2 - 0.1, size.z - 0.1, -size.y / 2 + 0.1]}
              name="stepper_y"
              label="Y (B belt)"
              onClick={() => handleClick('stepper_y')}
            />
            <Stepper
              position={[-size.x / 2 + 0.1, size.z - 0.1, size.y / 2 - 0.1]}
              name="stepper_y1"
              label="Y1 (B belt)"
              onClick={() => handleClick('stepper_y1')}
            />
            <Stepper
              position={[size.x / 2 - 0.1, size.z - 0.1, size.y / 2 - 0.1]}
              name="stepper_x1"
              label="X1 (A belt)"
              onClick={() => handleClick('stepper_x1')}
            />

            {/* Dynamic Z Motors */}
            <ZMotors size={size} zMotorCount={zMotorCount} onClick={handleClick} />

            {/* MCU Board - upright on back wall */}
            <MCUBoard 
              position={[0, size.z * 0.4, -size.y / 2 + 0.03]} 
              boardData={boardData}
              onMcuClick={() => handleClick('mcu')} 
              onPortClick={handlePortClick}
            />
          </group>
        );

      default:
        return (
          <mesh>
            <boxGeometry args={[1, 1, 1]} />
            <meshStandardMaterial color="#ef4444" />
          </mesh>
        );
    }
  };

  return (
    <>
      {/* Lighting */}
      <ambientLight intensity={0.4} />
      <directionalLight position={[5, 10, 5]} intensity={0.8} castShadow />
      <directionalLight position={[-5, 5, -5]} intensity={0.3} />
      <pointLight position={[0, 2, 0]} intensity={0.2} />

      {/* Environment for reflections */}
      <Environment preset="city" />

      {/* Ground grid */}
      <Grid
        position={[0, -0.01, 0]}
        args={[10, 10]}
        cellSize={0.2}
        cellThickness={0.5}
        cellColor="#334155"
        sectionSize={1}
        sectionThickness={1}
        sectionColor="#475569"
        fadeDistance={8}
        fadeStrength={1}
        followCamera={false}
      />

      {/* The printer model */}
      {renderModel()}
      
      {/* Camera animation controller */}
      <CameraController 
        targetPosition={shouldZoomToBoard ? boardCameraPosition : null} 
        enabled={!!shouldZoomToBoard} 
      />

      {/* Controls */}
      <OrbitControls
        makeDefault
        minPolarAngle={0.1}
        maxPolarAngle={Math.PI / 2 - 0.1}
        minDistance={1}
        maxDistance={5}
        enablePan={true}
        panSpeed={0.5}
      />
    </>
  );
}

export function PrinterScene({ modelType }: PrinterSceneProps) {
  return (
    <Canvas
      camera={{ position: [2, 1.5, 2], fov: 50 }}
      shadows
      dpr={[1, 2]}
    >
      <SceneContent modelType={modelType} />
    </Canvas>
  );
}
