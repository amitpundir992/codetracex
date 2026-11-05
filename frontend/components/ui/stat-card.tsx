'use client';

import React, { useEffect, useState } from 'react';
import { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

interface StatCardProps {
  icon: LucideIcon;
  label: string;
  value: string | number;
  color: 'blue' | 'purple' | 'green' | 'orange';
  className?: string;
  animate?: boolean;
}

const colorClasses = {
  blue: {
    bg: 'from-blue-50 to-blue-100 dark:from-blue-950/50 dark:to-blue-900/50',
    icon: 'text-blue-600 dark:text-blue-400',
    text: 'text-blue-900 dark:text-blue-100',
    iconBg: 'bg-blue-100 dark:bg-blue-900/50',
    border: 'border-blue-200 dark:border-blue-800',
    shadow: 'shadow-blue-500/5',
  },
  purple: {
    bg: 'from-purple-50 to-purple-100 dark:from-purple-950/50 dark:to-purple-900/50',
    icon: 'text-purple-600 dark:text-purple-400',
    text: 'text-purple-900 dark:text-purple-100',
    iconBg: 'bg-purple-100 dark:bg-purple-900/50',
    border: 'border-purple-200 dark:border-purple-800',
    shadow: 'shadow-purple-500/5',
  },
  green: {
    bg: 'from-green-50 to-green-100 dark:from-green-950/50 dark:to-green-900/50',
    icon: 'text-green-600 dark:text-green-400',
    text: 'text-green-900 dark:text-green-100',
    iconBg: 'bg-green-100 dark:bg-green-900/50',
    border: 'border-green-200 dark:border-green-800',
    shadow: 'shadow-green-500/5',
  },
  orange: {
    bg: 'from-orange-50 to-orange-100 dark:from-orange-950/50 dark:to-orange-900/50',
    icon: 'text-orange-600 dark:text-orange-400',
    text: 'text-orange-900 dark:text-orange-100',
    iconBg: 'bg-orange-100 dark:bg-orange-900/50',
    border: 'border-orange-200 dark:border-orange-800',
    shadow: 'shadow-orange-500/5',
  },
};

export const StatCard: React.FC<StatCardProps> = ({
  icon: Icon,
  label,
  value,
  color,
  className,
  animate = true,
}) => {
  const [displayValue, setDisplayValue] = useState<string | number>(animate ? 0 : value);
  const colors = colorClasses[color];

  useEffect(() => {
    if (!animate || typeof value !== 'number') {
      setDisplayValue(value);
      return;
    }

    const duration = 1000;
    const steps = 60;
    const stepValue = value / steps;
    let currentStep = 0;

    const timer = setInterval(() => {
      currentStep++;
      if (currentStep >= steps) {
        setDisplayValue(value);
        clearInterval(timer);
      } else {
        setDisplayValue(Math.floor(stepValue * currentStep));
      }
    }, duration / steps);

    return () => clearInterval(timer);
  }, [value, animate]);

  return (
    <div
      className={cn(
        'group relative p-6 rounded-2xl bg-gradient-to-br border transition-all duration-200',
        'hover:-translate-y-0.5 hover:shadow-md',
        colors.bg,
        colors.border,
        colors.shadow,
        className
      )}
    >
      <div className="flex items-start justify-between mb-3">
        <div className={cn('p-2 rounded-lg', colors.iconBg)}>
          <Icon className={cn('w-5 h-5', colors.icon)} />
        </div>
      </div>
      <div>
        <p className={cn('text-xs font-semibold uppercase tracking-wider mb-2', colors.text, 'opacity-80')}>
          {label}
        </p>
        <p className={cn('text-3xl font-bold', colors.text)}>
          {typeof displayValue === 'number' ? displayValue.toLocaleString() : displayValue}
        </p>
      </div>
    </div>
  );
};
