interface Props {
  seed: number;
  label: string;
}

export default function ImageComparison({ seed, label }: Props) {
  const dots = Array.from({ length: 34 }, (_, index) => {
    const x = (index * 29 + seed * 13) % 100;
    const y = (index * 43 + seed * 7) % 100;
    const opacity = 0.12 + ((index + seed) % 6) * 0.08;
    return <circle key={index} cx={`${x}%`} cy={`${y}%`} r={(index % 3) + 0.6} fill={`rgba(255,255,255,${opacity})`} />;
  });

  return (
    <div className="ct-tile">
      <svg viewBox="0 0 240 180" role="img" aria-label={label}>
        <defs>
          <radialGradient id={`lung-${seed}`} cx="50%" cy="50%" r="55%">
            <stop offset="0%" stopColor="#475569" />
            <stop offset="100%" stopColor="#020617" />
          </radialGradient>
        </defs>
        <rect width="240" height="180" rx="18" fill={`url(#lung-${seed})`} />
        <ellipse cx="82" cy="92" rx="44" ry="64" fill="rgba(15,23,42,0.72)" stroke="rgba(226,232,240,0.24)" />
        <ellipse cx="158" cy="92" rx="44" ry="64" fill="rgba(15,23,42,0.72)" stroke="rgba(226,232,240,0.24)" />
        <circle cx={seed % 2 === 0 ? 97 : 147} cy={seed % 3 === 0 ? 74 : 108} r={6 + (seed % 5)} fill="#fbbf24" opacity="0.9" />
        <circle cx={seed % 2 === 0 ? 97 : 147} cy={seed % 3 === 0 ? 74 : 108} r={14 + (seed % 4)} fill="none" stroke="#f97316" strokeDasharray="4 4" />
        {dots}
      </svg>
      <span>{label}</span>
    </div>
  );
}
