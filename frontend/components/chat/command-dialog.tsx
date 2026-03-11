"use client";

import { Fragment } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { X, UtensilsCrossed, Calendar, Users, HelpCircle } from 'lucide-react';

interface CommandOption {
  id: string;
  label: string;
  description: string;
  icon: React.ReactNode;
}

interface CommandDialogProps {
  isOpen: boolean;
  onClose: () => void;
  command: 'menu' | 'events' | null;
  onSelect: (value: string) => void;
}

const MENU_OPTIONS: CommandOption[] = [
  {
    id: 'wedding',
    label: 'Wedding Menu',
    description: 'Elegant options for your special day',
    icon: <UtensilsCrossed className="w-5 h-5" />,
  },
  {
    id: 'corporate',
    label: 'Corporate Event',
    description: 'Professional catering for business events',
    icon: <Users className="w-5 h-5" />,
  },
  {
    id: 'casual',
    label: 'Casual Gathering',
    description: 'Relaxed dining for informal events',
    icon: <UtensilsCrossed className="w-5 h-5" />,
  },
  {
    id: 'formal',
    label: 'Formal Dinner',
    description: 'Sophisticated multi-course dining',
    icon: <UtensilsCrossed className="w-5 h-5" />,
  },
];

const EVENT_OPTIONS: CommandOption[] = [
  {
    id: 'wedding',
    label: 'Wedding',
    description: 'Celebrate your special day',
    icon: <Calendar className="w-5 h-5" />,
  },
  {
    id: 'corporate',
    label: 'Corporate Event',
    description: 'Business meetings and conferences',
    icon: <Users className="w-5 h-5" />,
  },
  {
    id: 'birthday',
    label: 'Birthday Party',
    description: 'Make birthdays memorable',
    icon: <Calendar className="w-5 h-5" />,
  },
  {
    id: 'anniversary',
    label: 'Anniversary',
    description: 'Celebrate milestones together',
    icon: <Calendar className="w-5 h-5" />,
  },
  {
    id: 'graduation',
    label: 'Graduation',
    description: 'Honor academic achievements',
    icon: <Calendar className="w-5 h-5" />,
  },
  {
    id: 'other',
    label: 'Other Event',
    description: 'Custom event catering',
    icon: <Calendar className="w-5 h-5" />,
  },
];

export function CommandDialog({ isOpen, onClose, command, onSelect }: CommandDialogProps) {
  const options = command === 'menu' ? MENU_OPTIONS : EVENT_OPTIONS;
  const title = command === 'menu' ? 'Select Menu Type' : 'Select Event Type';

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/30 backdrop-blur-sm" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-2xl bg-white shadow-xl transition-all">
                <div className="relative bg-gradient-to-r from-blue-500 to-purple-600 p-6">
                  <Dialog.Title className="text-lg font-semibold text-white">
                    {title}
                  </Dialog.Title>
                  <button
                    onClick={onClose}
                    className="absolute right-4 top-4 text-white/80 hover:text-white transition"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <div className="p-2 max-h-[60vh] overflow-y-auto">
                  <div className="space-y-1">
                    {options.map((option) => (
                      <button
                        key={option.id}
                        onClick={() => {
                          onSelect(option.label);
                          onClose();
                        }}
                        className="w-full flex items-start gap-4 p-4 rounded-xl hover:bg-gray-50 transition text-left group"
                      >
                        <div className="mt-0.5 text-gray-600 group-hover:text-blue-600 transition">
                          {option.icon}
                        </div>
                        <div className="flex-1">
                          <h3 className="font-semibold text-gray-900 group-hover:text-blue-600 transition">
                            {option.label}
                          </h3>
                          <p className="text-sm text-gray-600 mt-0.5">{option.description}</p>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}
