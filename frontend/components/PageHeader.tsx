import type { ReactNode } from 'react';

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
};

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
}: PageHeaderProps) {
  return (
    <header className={`list-page-head page-head${className ? ` ${className}` : ''}`}>
      <div>
        {kicker ? <p className={kickerClassName || 'page-kicker'}>{kicker}</p> : null}
        <h1 className={titleClassName}>{title}</h1>
        {subtitle ? <p className={subtitleClassName || 'muted page-sub'}>{subtitle}</p> : null}
        {children}
      </div>
      {actions ? <div className="page-head-actions">{actions}</div> : null}
    </header>
  );
}
