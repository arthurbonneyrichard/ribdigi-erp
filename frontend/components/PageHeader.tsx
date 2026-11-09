import type { ReactNode } from 'react';
import DeskIcon from './DeskIcon';

type PageHeaderProps = {
  title: string;
  subtitle?: string;
  kicker?: string;
  actions?: ReactNode;
  children?: ReactNode;
  titleClassName?: string;
  kickerClassName?: string;
  subtitleClassName?: string;
  className?: string;
  /** DeskIcon name for the title card. Picked from the title when left out. */
  icon?: string;
};

// The first word that matches the title picks the picture on the title card.
const TITLE_ICONS: [string, string][] = [
  ['pos', 'cart'],
  ['till', 'cart'],
  ['bill', 'receipt'],
  ['invoice', 'receipt'],
  ['sale', 'receipt'],
  ['order', 'receipt'],
  ['purchas', 'truck'],
  ['supplier', 'truck'],
  ['deliver', 'truck'],
  ['inventory', 'box'],
  ['stock', 'box'],
  ['product', 'box'],
  ['store', 'map'],
  ['branch', 'map'],
  ['department', 'map'],
  ['expense', 'wallet'],
  ['credit', 'wallet'],
  ['account', 'cash'],
  ['tax', 'cash'],
  ['billing', 'cash'],
  ['gift', 'tag'],
  ['report', 'chart'],
  ['customer', 'users'],
  ['user', 'users'],
  ['staff', 'users'],
  ['notification', 'alert'],
  ['audit', 'search'],
  ['security', 'check'],
  ['backup', 'download'],
  ['printer', 'print'],
  ['support', 'phone'],
  ['help', 'phone'],
  ['hotel', 'home'],
  ['room', 'home'],
  ['restaurant', 'flame'],
  ['kitchen', 'flame'],
  ['company', 'home'],
  ['front desk', 'door'],
  ['reservation', 'calendar'],
  ['booking', 'calendar'],
  ['event', 'calendar'],
  ['housekeeping', 'check'],
  ['maintenance', 'alert'],
  ['lost', 'search'],
  ['guest', 'users'],
  ['night', 'clock'],
  ['rate', 'tag'],
  ['menu', 'tag'],
  ['recipe', 'flame'],
  ['ingredient', 'box'],
  ['waste', 'trash'],
  ['money', 'cash'],
  ['cash', 'cash'],
  ['profit', 'chart'],
  ['table', 'calendarCheck'],
  ['integration', 'arrow'],
];

function iconFor(title: string): string {
  const lower = title.toLowerCase();
  return TITLE_ICONS.find(([word]) => lower.includes(word))?.[1] || 'chart';
}

export default function PageHeader({
  title,
  subtitle,
  kicker,
  actions,
  children,
  titleClassName,
  kickerClassName,
  subtitleClassName,
  className,
  icon,
}: PageHeaderProps) {
  return (
    <header className={`list-page-head page-head page-head-card${className ? ` ${className}` : ''}`}>
      <span className="page-head-ico" aria-hidden="true">
        <DeskIcon name={icon || iconFor(title)} size={24} />
      </span>
      <div className="page-head-text">
        {kicker ? <p className={kickerClassName || 'page-kicker'}>{kicker}</p> : null}
        <h1 className={titleClassName}>{title}</h1>
        {subtitle ? <p className={subtitleClassName || 'muted page-sub'}>{subtitle}</p> : null}
        {children}
      </div>
      {actions ? <div className="page-head-actions">{actions}</div> : null}
    </header>
  );
}
