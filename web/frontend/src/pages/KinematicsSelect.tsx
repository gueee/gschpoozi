import { useNavigate } from 'react-router-dom';
import useWizardStore from '../stores/wizardStore';
import { Printer, Box, Triangle, Cog, type LucideIcon } from 'lucide-react';

interface KinematicsOption {
  id: string;
  name: string;
  description: string;
  model: string;
  icon: LucideIcon;
  examples: string[];
  color: string;
}

const KINEMATICS_OPTIONS: KinematicsOption[] = [
  {
    id: 'corexy',
    name: 'CoreXY',
    description: 'Fixed bed with dual motor XY movement. Fast and precise.',
    model: 'voron',
    icon: Box,
    examples: ['Voron', 'RatRig', 'Annex'],
    color: 'from-cyan-500 to-blue-600',
  },
  {
    id: 'cartesian',
    name: 'Cartesian',
    description: 'Traditional bed-slinger or moving gantry design.',
    model: 'ender',
    icon: Printer,
    examples: ['Ender 3', 'Prusa MK3', 'CR-10'],
    color: 'from-emerald-500 to-teal-600',
  },
  {
    id: 'delta',
    name: 'Delta',
    description: 'Three tower design with moving effector. Extremely fast.',
    model: 'kossel',
    icon: Triangle,
    examples: ['Kossel', 'Anycubic Predator', 'Flsun'],
    color: 'from-violet-500 to-purple-600',
  },
  {
    id: 'hybrid_corexy',
    name: 'Hybrid CoreXY (AWD)',
    description: 'CoreXY with 4 XY motors for extra power and speed.',
    model: 'vzbot',
    icon: Cog,
    examples: ['VzBot', 'Micron+', 'Trident AWD'],
    color: 'from-orange-500 to-red-600',
  },
];

export function KinematicsSelect() {
  const navigate = useNavigate();
  const setField = useWizardStore((state) => state.setField);

  const handleSelectKinematics = (option: KinematicsOption) => {
    setField('printer.kinematics', option.id);
    setField('printer.model', option.model);
    // Enable AWD flag for hybrid_corexy (needed for stepper X1/Y1 config generation)
    setField('printer.awd_enabled', option.id === 'hybrid_corexy');
    navigate('/configurator');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Background Pattern */}
      <div className="absolute inset-0 opacity-5">
        <div
          className="absolute inset-0"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
          }}
        />
      </div>

      <div className="relative z-10 flex flex-col items-center justify-center min-h-screen p-4 sm:p-8">
        {/* Logo / Title */}
        <div className="text-center mb-12">
          <h1 className="text-5xl sm:text-6xl font-black text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-blue-400 to-violet-400 mb-4">
            gschpoozi
          </h1>
          <p className="text-xl text-slate-400 font-light">
            Klipper Configuration Wizard
          </p>
        </div>

        {/* Subtitle */}
        <div className="text-center mb-12 max-w-2xl">
          <h2 className="text-2xl font-semibold text-white mb-3">
            Select Your Printer Kinematics
          </h2>
          <p className="text-slate-400">
            Choose the motion system that best describes your 3D printer.
            This will load an interactive 3D model to help you configure every component.
          </p>
        </div>

        {/* Kinematics Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 w-full max-w-6xl">
          {KINEMATICS_OPTIONS.map((option) => {
            const Icon = option.icon;
            return (
              <button
                key={option.id}
                className="group relative flex flex-col items-center p-8 bg-slate-800/50 backdrop-blur-sm rounded-2xl border border-slate-700 hover:border-slate-500 transition-all duration-300 ease-out transform hover:-translate-y-2 hover:shadow-2xl hover:shadow-cyan-500/10"
                onClick={() => handleSelectKinematics(option)}
              >
                {/* Gradient background on hover */}
                <div
                  className={`absolute inset-0 bg-gradient-to-br ${option.color} opacity-0 group-hover:opacity-10 rounded-2xl transition-opacity duration-300`}
                />

                {/* Icon */}
                <div
                  className={`relative w-20 h-20 rounded-2xl bg-gradient-to-br ${option.color} flex items-center justify-center mb-6 shadow-lg`}
                >
                  <Icon className="text-white" size={40} strokeWidth={1.5} />
                </div>

                {/* Title */}
                <h3 className="relative text-xl font-bold text-white mb-2 group-hover:text-cyan-300 transition-colors">
                  {option.name}
                </h3>

                {/* Description */}
                <p className="relative text-sm text-slate-400 text-center mb-4">
                  {option.description}
                </p>

                {/* Examples */}
                <div className="relative flex flex-wrap justify-center gap-2">
                  {option.examples.map((example) => (
                    <span
                      key={example}
                      className="text-xs px-2 py-1 bg-slate-700/50 text-slate-300 rounded-full"
                    >
                      {example}
                    </span>
                  ))}
                </div>

                {/* Arrow indicator */}
                <div className="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
                  <svg
                    className="w-6 h-6 text-cyan-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M13 7l5 5m0 0l-5 5m5-5H6"
                    />
                  </svg>
                </div>
              </button>
            );
          })}
        </div>

        {/* Footer note */}
        <div className="mt-12 text-center text-sm text-slate-500">
          <p>Don't see your kinematics? Most printers fit into one of these categories.</p>
          <p className="mt-1">
            CoreXZ and other variants can be configured after selection.
          </p>
        </div>
      </div>
    </div>
  );
}
