'use client';

import React from 'react';
import { cn } from '@/lib/utils';

interface ExampleChipProps {
  label: string;
  onClick: () => void;
  className?: string;
}

export const ExampleChip: React.FC<ExampleChipProps> = ({ label, onClick, className }) => {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'px-4 py-2 rounded-full text-sm font-medium transition-all duration-150',
        'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300',
        'hover:bg-indigo-50 dark:hover:bg-indigo-950/50',
        'hover:text-indigo-600 dark:hover:text-indigo-400',
        'hover:border-indigo-200 dark:hover:border-indigo-800',
        'border border-transparent',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2',
        className
      )}
    >
      {label}
    </button>
  );
};
