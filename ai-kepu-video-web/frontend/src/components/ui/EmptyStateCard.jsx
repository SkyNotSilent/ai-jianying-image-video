import { useId } from 'react'

const VALID_VARIANTS = new Set(['manuscript', 'projects', 'media', 'voice', 'configuration'])

function Artwork({ variant }) {
  if (variant === 'projects') {
    return <>
      <rect className="ui-empty-paper" x="29" y="25" width="102" height="74" rx="3" />
      <path className="ui-empty-rule" d="M42 43h30M42 51h18" />
      <rect className="ui-empty-frame" x="42" y="62" width="32" height="22" rx="2" />
      <rect className="ui-empty-frame" x="84" y="62" width="32" height="22" rx="2" />
      <path className="ui-empty-accent" d="m49 78 7-7 5 5 5-6 5 8M91 78l7-9 11 9" />
      <path className="ui-empty-note" d="M94 43h21M94 51h14" />
    </>
  }

  if (variant === 'voice') {
    return <>
      <rect className="ui-empty-paper" x="29" y="25" width="102" height="74" rx="3" />
      <path className="ui-empty-rule" d="M42 43h45M42 51h29" />
      <path className="ui-empty-wave" d="M42 73h7l4-12 7 25 7-19 7 12 6-7 6 6h7l5-15 7 23 6-13h7" />
      <circle className="ui-empty-accent-fill" cx="113" cy="44" r="7" />
      <path className="ui-empty-paper-mark" d="M110 44h6M113 41v6" />
    </>
  }

  if (variant === 'configuration') {
    return <>
      <rect className="ui-empty-paper" x="29" y="25" width="102" height="74" rx="3" />
      <path className="ui-empty-rule" d="M42 42h31M42 50h19" />
      <path className="ui-empty-note" d="M42 69h76M42 83h76" />
      <circle className="ui-empty-accent-fill" cx="78" cy="69" r="5" />
      <circle className="ui-empty-accent-fill" cx="101" cy="83" r="5" />
      <path className="ui-empty-paper-mark" d="M78 64v10M101 78v10" />
    </>
  }

  if (variant === 'media') {
    return <>
      <rect className="ui-empty-paper" x="29" y="25" width="102" height="74" rx="3" />
      <rect className="ui-empty-frame" x="42" y="40" width="76" height="45" rx="2" />
      <path className="ui-empty-accent" d="m48 78 17-18 12 11 10-9 24 16" />
      <circle className="ui-empty-accent-fill" cx="99" cy="51" r="5" />
      <path className="ui-empty-note" d="M50 91h60" />
    </>
  }

  return <>
    <path className="ui-empty-paper-back" d="m35 28 91-7 7 73-91 7Z" />
    <rect className="ui-empty-paper" x="29" y="25" width="102" height="74" rx="3" />
    <path className="ui-empty-rule" d="M42 43h53M42 52h67M42 61h60M42 70h44" />
    <path className="ui-empty-accent" d="M42 83c12-8 21 6 33-1 8-5 15-12 25-7 6 3 9 6 17 3" />
    <path className="ui-empty-pencil" d="m105 39 16-16 6 6-16 16-9 3Z" />
    <path className="ui-empty-paper-mark" d="m105 39 6 6M121 23l6 6" />
  </>
}

export function EditorialLineIllustration({ variant = 'manuscript', className = '' }) {
  const resolvedVariant = VALID_VARIANTS.has(variant) ? variant : 'manuscript'
  return (
    <svg
      className={`ui-empty-illustration${className ? ` ${className}` : ''}`}
      data-variant={resolvedVariant}
      viewBox="0 0 160 120"
      aria-hidden="true"
      focusable="false"
    >
      <path className="ui-empty-registration" d="M18 29v-9h9M133 20h9v9M18 91v9h9M142 91v9h-9" />
      <Artwork variant={resolvedVariant} />
      <text className="ui-empty-folio" x="20" y="113">INSIGHT / 01</text>
      <path className="ui-empty-folio-rule" d="M91 110h49" />
    </svg>
  )
}

export function EmptyStateCard({
  as: Tag = 'section',
  variant = 'manuscript',
  eyebrow = '创作工作台',
  title = '暂无内容',
  description = '开始创作后，内容会出现在这里。',
  action,
  children,
  compact = false,
  className = '',
  ...props
}) {
  const titleId = useId()
  const inline = Tag === 'span'
  const TitleTag = inline ? 'strong' : 'h2'
  const DescriptionTag = inline ? 'span' : 'p'
  const CopyTag = inline ? 'span' : 'div'
  const ActionTag = inline ? 'span' : 'div'

  return (
    <Tag
      className={`ui-empty-state${compact ? ' is-compact' : ''}${className ? ` ${className}` : ''}`}
      aria-labelledby={titleId}
      {...props}
    >
      <EditorialLineIllustration variant={variant} />
      <CopyTag className="ui-empty-copy">
        {eyebrow ? <span className="ui-empty-eyebrow">{eyebrow}</span> : null}
        <TitleTag id={titleId}>{title}</TitleTag>
        {description ? <DescriptionTag className="ui-empty-description">{description}</DescriptionTag> : null}
        {children}
        {action ? <ActionTag className="ui-empty-action">{action}</ActionTag> : null}
      </CopyTag>
    </Tag>
  )
}
