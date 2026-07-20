"use client";

import { Suspense, useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Environment, Lightformer } from "@react-three/drei";
import * as THREE from "three";
import { MOSAIC_CASES } from "@/lib/mosaic-cases";

type FacetLayout = {
  id: string;
  position: [number, number, number];
  scale: number;
  rotation: [number, number, number];
  roughness: number;
  metalness: number;
  clearcoat: number;
};

// Deterministic pseudo-random so the cluster layout is stable across renders.
function seededRandom(seed: number) {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

function buildLayout(count: number): FacetLayout[] {
  const rand = seededRandom(42);
  const layout: FacetLayout[] = [];
  for (let i = 0; i < count; i++) {
    const theta = rand() * Math.PI * 2;
    const phi = Math.acos(2 * rand() - 1);
    const r = 1.1 + rand() * 0.6;
    layout.push({
      id: MOSAIC_CASES[i].id,
      position: [
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.sin(phi) * Math.sin(theta) * 0.8,
        r * Math.cos(phi),
      ],
      scale: 0.42 + rand() * 0.3,
      rotation: [rand() * Math.PI, rand() * Math.PI, rand() * Math.PI],
      // Small per-facet material variance so the cluster doesn't read as
      // one uniform surface — each piece catches light a little differently.
      roughness: 0.14 + rand() * 0.24,
      metalness: 0.22 + rand() * 0.28,
      clearcoat: 0.35 + rand() * 0.45,
    });
  }
  return layout;
}

function Facet({
  layout,
  isActive,
  onSelect,
}: {
  layout: FacetLayout;
  isActive: boolean;
  onSelect: (id: string) => void;
}) {
  const [hovered, setHovered] = useState(false);
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame(() => {
    if (!meshRef.current) return;
    const target = hovered || isActive ? layout.scale * 1.15 : layout.scale;
    meshRef.current.scale.setScalar(
      THREE.MathUtils.lerp(meshRef.current.scale.x, target, 0.15)
    );
  });

  return (
    <mesh
      ref={meshRef}
      position={layout.position}
      rotation={layout.rotation}
      onPointerOver={(e) => {
        e.stopPropagation();
        setHovered(true);
        onSelect(layout.id);
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={(e) => {
        e.stopPropagation();
        setHovered(false);
        document.body.style.cursor = "auto";
      }}
      onClick={(e) => {
        e.stopPropagation();
        onSelect(layout.id);
      }}
    >
      <icosahedronGeometry args={[1, 0]} />
      <meshPhysicalMaterial
        color={hovered || isActive ? "#fafafa" : "#bcbcbc"}
        flatShading
        roughness={layout.roughness}
        metalness={layout.metalness}
        clearcoat={layout.clearcoat}
        clearcoatRoughness={0.25}
        envMapIntensity={hovered || isActive ? 1.6 : 1.1}
      />
    </mesh>
  );
}

function ClusterGroup({
  activeId,
  onSelect,
}: {
  activeId: string;
  onSelect: (id: string) => void;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const layout = useMemo(() => buildLayout(MOSAIC_CASES.length), []);

  useFrame((_, delta) => {
    if (!groupRef.current) return;
    groupRef.current.rotation.y += delta * 0.09;
    groupRef.current.rotation.x = Math.sin(Date.now() * 0.00015) * 0.08;
  });

  return (
    <group ref={groupRef}>
      {layout.map((l) => (
        <Facet
          key={l.id}
          layout={l}
          isActive={l.id === activeId}
          onSelect={onSelect}
        />
      ))}
    </group>
  );
}

export default function CaseCluster({
  activeId,
  onSelect,
}: {
  activeId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="h-[420px] w-full sm:h-[520px] lg:h-[580px]">
      <Canvas camera={{ position: [0, 0, 4.2], fov: 42 }} dpr={[1, 1.75]}>
        <ambientLight intensity={0.35} />
        <directionalLight position={[3, 4, 5]} intensity={0.7} />
        <directionalLight position={[-4, -2, -3]} intensity={0.2} />
        <Suspense fallback={null}>
          <Environment resolution={256}>
            <Lightformer intensity={2.5} color="#ffffff" position={[4, 4, 4]} scale={[6, 6, 1]} />
            <Lightformer intensity={1.2} color="#cccccc" position={[-4, 2, -3]} scale={[5, 5, 1]} />
            <Lightformer intensity={1.8} color="#ffffff" position={[0, -4, 2]} scale={[8, 3, 1]} />
          </Environment>
        </Suspense>
        <ClusterGroup activeId={activeId} onSelect={onSelect} />
      </Canvas>
    </div>
  );
}
