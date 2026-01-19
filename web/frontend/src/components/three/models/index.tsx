import { useRef, useState, Suspense } from 'react';
import { useGLTF } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import type { ThreeEvent } from '@react-three/fiber';
import * as THREE from 'three';
import { Html } from '@react-three/drei';
import useWizardStore from '../../../stores/wizardStore';

// Common props for interactive model components
interface InteractiveModelProps {
  position: [number, number, number];
  rotation?: [number, number, number];
  scale?: number | [number, number, number];
  name: string;
  label: string;
  onClick: () => void;
  color?: string;
  hoverColor?: string;
  selectedColor?: string;
}

// Shared hook for interactive behavior
function useInteractive(
  name: string,
  color: string,
  hoverColor: string,
  selectedColor: string
) {
  const ref = useRef<THREE.Group>(null);
  const [hovered, setHovered] = useState(false);
  const activePanel = useWizardStore((state) => state.activePanel);
  const isSelected = activePanel === name;

  useFrame(() => {
    if (ref.current) {
      // Subtle pulse when selected
      if (isSelected) {
        ref.current.scale.setScalar(1 + Math.sin(Date.now() * 0.005) * 0.02);
      } else {
        ref.current.scale.lerp(new THREE.Vector3(1, 1, 1), 0.1);
      }
    }
  });

  const targetColor = isSelected ? selectedColor : hovered ? hoverColor : color;

  return {
    ref,
    hovered,
    setHovered,
    isSelected,
    targetColor,
  };
}

// Panels that show the board schematic (should hide model labels)
const BOARD_SCHEMATIC_PANELS = [
  'stepper_x', 'stepper_y', 'stepper_z', 'stepper_z1', 'stepper_z2', 'stepper_z3',
  'stepper_x1', 'stepper_y1', 'extruder', 'fans', 'heater_bed', 'hotend', 'probe'
];

// Label component for hover/selected state
function ModelLabel({
  label,
  isSelected,
  show,
  position = [0, 0.1, 0],
}: {
  label: string;
  isSelected: boolean;
  show: boolean;
  position?: [number, number, number];
}) {
  const activePanel = useWizardStore((state) => state.activePanel);
  
  // Hide labels when board schematic is shown (to avoid overlapping labels)
  const isBoardSchematicVisible = activePanel && BOARD_SCHEMATIC_PANELS.includes(activePanel);
  
  if (!show || isBoardSchematicVisible) return null;

  return (
    <Html position={position} center distanceFactor={4}>
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
  );
}

// ============================================
// NEMA17 Stepper Motor
// ============================================

function StepperMotorFallback({
  position,
  rotation,
  scale = 1,
  name,
  label,
  onClick,
  color = '#374151',
  hoverColor = '#3b82f6',
  selectedColor = '#60a5fa',
}: InteractiveModelProps) {
  const { ref, hovered, setHovered, isSelected, targetColor } = useInteractive(
    name,
    color,
    hoverColor,
    selectedColor
  );

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

  const scaleArray = typeof scale === 'number' ? [scale, scale, scale] : scale;

  return (
    <group
      ref={ref}
      position={position}
      rotation={rotation}
      scale={scaleArray as [number, number, number]}
      onPointerOver={handlePointerOver}
      onPointerOut={handlePointerOut}
      onClick={handleClick}
    >
      {/* NEMA17 body - 42x42x40mm with rounded corners feel */}
      <mesh>
        <boxGeometry args={[0.042, 0.040, 0.042]} />
        <meshStandardMaterial color={targetColor} metalness={0.6} roughness={0.4} />
      </mesh>

      {/* Front face plate (darker) */}
      <mesh position={[0, 0.0205, 0]}>
        <boxGeometry args={[0.042, 0.001, 0.042]} />
        <meshStandardMaterial color="#1f2937" metalness={0.7} roughness={0.3} />
      </mesh>

      {/* Motor shaft */}
      <mesh position={[0, 0.032, 0]}>
        <cylinderGeometry args={[0.0025, 0.0025, 0.024, 16]} />
        <meshStandardMaterial color="#9ca3af" metalness={0.9} roughness={0.1} />
      </mesh>

      {/* Shaft collar */}
      <mesh position={[0, 0.022, 0]}>
        <cylinderGeometry args={[0.011, 0.011, 0.002, 32]} />
        <meshStandardMaterial color="#6b7280" metalness={0.8} roughness={0.2} />
      </mesh>

      {/* Mounting holes (decorative) */}
      {[
        [-0.0155, 0.0206, -0.0155],
        [0.0155, 0.0206, -0.0155],
        [-0.0155, 0.0206, 0.0155],
        [0.0155, 0.0206, 0.0155],
      ].map((pos, i) => (
        <mesh key={i} position={pos as [number, number, number]}>
          <cylinderGeometry args={[0.002, 0.002, 0.002, 8]} />
          <meshStandardMaterial color="#111827" />
        </mesh>
      ))}

      {/* Back connector */}
      <mesh position={[0, -0.024, 0]}>
        <boxGeometry args={[0.015, 0.008, 0.02]} />
        <meshStandardMaterial color="#1f2937" />
      </mesh>

      <ModelLabel label={label} isSelected={isSelected} show={hovered || isSelected} position={[0, 0.05, 0]} />
    </group>
  );
}

function StepperMotorGLTF({
  position,
  rotation,
  scale = 1,
  name,
  label,
  onClick,
  color = '#374151',
  hoverColor = '#3b82f6',
  selectedColor = '#60a5fa',
}: InteractiveModelProps) {
  const { scene } = useGLTF('/models/nema17.glb');
  const { ref, hovered, setHovered, isSelected, targetColor } = useInteractive(
    name,
    color,
    hoverColor,
    selectedColor
  );

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

  // Clone the scene to allow multiple instances
  const clonedScene = scene.clone();

  // Apply color to all meshes
  clonedScene.traverse((child) => {
    if (child instanceof THREE.Mesh) {
      child.material = new THREE.MeshStandardMaterial({
        color: targetColor,
        metalness: 0.6,
        roughness: 0.4,
      });
    }
  });

  // Scale from mm to scene units (0.001 = 1mm)
  const modelScale = typeof scale === 'number' ? scale * 0.001 : scale.map(s => s * 0.001);

  return (
    <group
      ref={ref}
      position={position}
      rotation={rotation}
      scale={modelScale as [number, number, number]}
      onPointerOver={handlePointerOver}
      onPointerOut={handlePointerOut}
      onClick={handleClick}
    >
      <primitive object={clonedScene} />
      <ModelLabel label={label} isSelected={isSelected} show={hovered || isSelected} position={[0, 50, 0]} />
    </group>
  );
}

// Export with fallback
export function StepperMotorModel(props: InteractiveModelProps) {
  const [useGltf, setUseGltf] = useState(true);

  if (!useGltf) {
    return <StepperMotorFallback {...props} />;
  }

  return (
    <Suspense fallback={<StepperMotorFallback {...props} />}>
      <ErrorBoundary onError={() => setUseGltf(false)}>
        <StepperMotorGLTF {...props} />
      </ErrorBoundary>
    </Suspense>
  );
}

// ============================================
// Extruder (Cold End)
// ============================================

function ExtruderFallback({
  position,
  rotation,
  scale = 1,
  name,
  label,
  onClick,
  color = '#475569',
  hoverColor = '#8b5cf6',
  selectedColor = '#a78bfa',
}: InteractiveModelProps) {
  const { ref, hovered, setHovered, isSelected, targetColor } = useInteractive(
    name,
    color,
    hoverColor,
    selectedColor
  );

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

  const scaleArray = typeof scale === 'number' ? [scale, scale, scale] : scale;

  return (
    <group
      ref={ref}
      position={position}
      rotation={rotation}
      scale={scaleArray as [number, number, number]}
      onPointerOver={handlePointerOver}
      onPointerOut={handlePointerOut}
      onClick={handleClick}
    >
      {/* Main extruder body (BMG-style dual gear) */}
      <mesh position={[0, 0, 0]}>
        <boxGeometry args={[0.045, 0.055, 0.025]} />
        <meshStandardMaterial color={targetColor} metalness={0.4} roughness={0.6} />
      </mesh>

      {/* Motor mount side */}
      <mesh position={[0.025, 0, 0]}>
        <boxGeometry args={[0.005, 0.042, 0.042]} />
        <meshStandardMaterial color="#1f2937" metalness={0.5} roughness={0.5} />
      </mesh>

      {/* Filament path indicator */}
      <mesh position={[0, 0.03, 0]}>
        <cylinderGeometry args={[0.002, 0.002, 0.015, 8]} />
        <meshStandardMaterial color="#fbbf24" metalness={0.3} roughness={0.7} />
      </mesh>

      {/* Gear housing bulge */}
      <mesh position={[-0.01, 0, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.015, 0.015, 0.02, 16]} />
        <meshStandardMaterial color={targetColor} metalness={0.5} roughness={0.5} />
      </mesh>

      {/* Tension arm */}
      <mesh position={[-0.025, 0.015, 0]}>
        <boxGeometry args={[0.008, 0.03, 0.015]} />
        <meshStandardMaterial color="#374151" metalness={0.4} roughness={0.6} />
      </mesh>

      <ModelLabel label={label} isSelected={isSelected} show={hovered || isSelected} position={[0, 0.05, 0]} />
    </group>
  );
}

function ExtruderGLTF({
  position,
  rotation,
  scale = 1,
  name,
  label,
  onClick,
  color = '#475569',
  hoverColor = '#8b5cf6',
  selectedColor = '#a78bfa',
}: InteractiveModelProps) {
  const { scene } = useGLTF('/models/extruder.glb');
  const { ref, hovered, setHovered, isSelected, targetColor } = useInteractive(
    name,
    color,
    hoverColor,
    selectedColor
  );

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

  const clonedScene = scene.clone();

  clonedScene.traverse((child) => {
    if (child instanceof THREE.Mesh) {
      child.material = new THREE.MeshStandardMaterial({
        color: targetColor,
        metalness: 0.4,
        roughness: 0.6,
      });
    }
  });

  const modelScale = typeof scale === 'number' ? scale * 0.001 : scale.map(s => s * 0.001);

  return (
    <group
      ref={ref}
      position={position}
      rotation={rotation}
      scale={modelScale as [number, number, number]}
      onPointerOver={handlePointerOver}
      onPointerOut={handlePointerOut}
      onClick={handleClick}
    >
      <primitive object={clonedScene} />
      <ModelLabel label={label} isSelected={isSelected} show={hovered || isSelected} position={[0, 40, 0]} />
    </group>
  );
}

export function ExtruderModel(props: InteractiveModelProps) {
  const [useGltf, setUseGltf] = useState(true);

  if (!useGltf) {
    return <ExtruderFallback {...props} />;
  }

  return (
    <Suspense fallback={<ExtruderFallback {...props} />}>
      <ErrorBoundary onError={() => setUseGltf(false)}>
        <ExtruderGLTF {...props} />
      </ErrorBoundary>
    </Suspense>
  );
}

// ============================================
// Hotend (Hot End)
// ============================================

function HotendFallback({
  position,
  rotation,
  scale = 1,
  name,
  label,
  onClick,
  color = '#475569',
  hoverColor = '#f97316',
  selectedColor = '#fb923c',
}: InteractiveModelProps) {
  const { ref, hovered, setHovered, isSelected, targetColor } = useInteractive(
    name,
    color,
    hoverColor,
    selectedColor
  );

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

  const scaleArray = typeof scale === 'number' ? [scale, scale, scale] : scale;

  return (
    <group
      ref={ref}
      position={position}
      rotation={rotation}
      scale={scaleArray as [number, number, number]}
      onPointerOver={handlePointerOver}
      onPointerOut={handlePointerOut}
      onClick={handleClick}
    >
      {/* Heatsink with fins */}
      <group position={[0, 0.02, 0]}>
        {/* Main heatsink body */}
        <mesh>
          <cylinderGeometry args={[0.011, 0.011, 0.026, 16]} />
          <meshStandardMaterial color={targetColor} metalness={0.7} roughness={0.3} />
        </mesh>
        {/* Heatsink fins */}
        {[-0.01, -0.005, 0, 0.005, 0.01].map((y, i) => (
          <mesh key={i} position={[0, y, 0]}>
            <cylinderGeometry args={[0.013, 0.013, 0.002, 16]} />
            <meshStandardMaterial color={targetColor} metalness={0.7} roughness={0.3} />
          </mesh>
        ))}
      </group>

      {/* Heatbreak (narrow section) */}
      <mesh position={[0, -0.002, 0]}>
        <cylinderGeometry args={[0.003, 0.003, 0.012, 8]} />
        <meshStandardMaterial color="#9ca3af" metalness={0.9} roughness={0.1} />
      </mesh>

      {/* Heater block */}
      <mesh position={[0, -0.018, 0]}>
        <boxGeometry args={[0.02, 0.012, 0.016]} />
        <meshStandardMaterial color="#b45309" metalness={0.6} roughness={0.4} />
      </mesh>

      {/* Heater cartridge */}
      <mesh position={[0.012, -0.018, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.003, 0.003, 0.015, 8]} />
        <meshStandardMaterial color="#1f2937" />
      </mesh>

      {/* Thermistor */}
      <mesh position={[-0.012, -0.018, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.0015, 0.0015, 0.008, 8]} />
        <meshStandardMaterial color="#065f46" />
      </mesh>

      {/* Nozzle */}
      <mesh position={[0, -0.032, 0]}>
        <coneGeometry args={[0.006, 0.015, 6]} />
        <meshStandardMaterial color="#b45309" metalness={0.8} roughness={0.2} />
      </mesh>

      {/* Nozzle tip */}
      <mesh position={[0, -0.042, 0]}>
        <coneGeometry args={[0.002, 0.005, 6]} />
        <meshStandardMaterial color="#92400e" metalness={0.9} roughness={0.1} />
      </mesh>

      <ModelLabel label={label} isSelected={isSelected} show={hovered || isSelected} position={[0, 0.05, 0]} />
    </group>
  );
}

function HotendGLTF({
  position,
  rotation,
  scale = 1,
  name,
  label,
  onClick,
  color = '#475569',
  hoverColor = '#f97316',
  selectedColor = '#fb923c',
}: InteractiveModelProps) {
  const { scene } = useGLTF('/models/hotend.glb');
  const { ref, hovered, setHovered, isSelected, targetColor } = useInteractive(
    name,
    color,
    hoverColor,
    selectedColor
  );

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

  const clonedScene = scene.clone();

  clonedScene.traverse((child) => {
    if (child instanceof THREE.Mesh) {
      child.material = new THREE.MeshStandardMaterial({
        color: targetColor,
        metalness: 0.6,
        roughness: 0.4,
      });
    }
  });

  const modelScale = typeof scale === 'number' ? scale * 0.001 : scale.map(s => s * 0.001);

  return (
    <group
      ref={ref}
      position={position}
      rotation={rotation}
      scale={modelScale as [number, number, number]}
      onPointerOver={handlePointerOver}
      onPointerOut={handlePointerOut}
      onClick={handleClick}
    >
      <primitive object={clonedScene} />
      <ModelLabel label={label} isSelected={isSelected} show={hovered || isSelected} position={[0, 50, 0]} />
    </group>
  );
}

export function HotendModel(props: InteractiveModelProps) {
  const [useGltf, setUseGltf] = useState(true);

  if (!useGltf) {
    return <HotendFallback {...props} />;
  }

  return (
    <Suspense fallback={<HotendFallback {...props} />}>
      <ErrorBoundary onError={() => setUseGltf(false)}>
        <HotendGLTF {...props} />
      </ErrorBoundary>
    </Suspense>
  );
}

// ============================================
// Error Boundary for GLTF loading failures
// ============================================

import { Component } from 'react';
import type { ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  onError: () => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch() {
    this.props.onError();
  }

  render() {
    if (this.state.hasError) {
      return null;
    }
    return this.props.children;
  }
}

// Preload models (call this early to start loading)
export function preloadModels() {
  try {
    useGLTF.preload('/models/nema17.glb');
    useGLTF.preload('/models/extruder.glb');
    useGLTF.preload('/models/hotend.glb');
  } catch {
    // Models not available, will use fallbacks
  }
}
