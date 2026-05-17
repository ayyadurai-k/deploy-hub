// Brand identity bits used across the app. The mark itself is the existing
// favicon.svg — same asset, vector, served by Vite at /favicon.svg — so the
// browser tab icon and the in-app logo stay visually identical.

type LogoProps = {
  size?: number;
  className?: string;
};

export function Logo({ size = 32, className = "" }: LogoProps) {
  return (
    <img
      src="/favicon.svg"
      width={size}
      height={size}
      alt=""
      className={className}
      draggable={false}
    />
  );
}

type WordmarkProps = {
  className?: string;
};

export function Wordmark({ className = "" }: WordmarkProps) {
  return (
    <span className={`font-semibold tracking-tight ${className}`}>
      Deploy<span className="text-violet-600">Hub</span>
    </span>
  );
}

type BrandProps = {
  size?: number;
  wordmark?: boolean;
  className?: string;
  textClassName?: string;
};

export function Brand({
  size = 28,
  wordmark = true,
  className = "",
  textClassName = "text-base",
}: BrandProps) {
  return (
    <div className={`inline-flex items-center gap-2.5 ${className}`}>
      <Logo size={size} />
      {wordmark && <Wordmark className={textClassName} />}
    </div>
  );
}
