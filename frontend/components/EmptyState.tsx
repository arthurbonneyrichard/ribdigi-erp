import type { ReactNode } from 'react';

type EmptyStateProps = {
  title: string;
  detail?: string;
  action?: ReactNode;
  role?: 'status' | 'alert';
  className?: string;
};

export default function EmptyState({ title, detail, action, role = 'status', className }: EmptyStateProps) {
  return (
    <div className={`page-empty${className ? ` ${className}` : ''}`} role={role}>
      <p className="page-empty-title">{title}</p>
      {detail ? <p className="muted">{detail}</p> : null}
      {action}
    </div>
  );
}
