import Image from "next/image";

/**
 * Titan Guardian logo on black: the approved artwork with "Guardian" in white
 * (web/public/brand/titan-guardian-dark.png, 1190x496). `size` is roughly the "Titan" cap height.
 */
export function GuardianMark({ size = 36, product = true }: { size?: number; product?: boolean }) {
  const height = Math.round(size * (product ? 1.55 : 1.15));
  const src = product ? "/brand/titan-guardian-dark.png" : "/brand/titan.png";
  const ratio = product ? 1190 / 496 : 1189 / 371;
  return (
    <Image
      src={src}
      alt={product ? "Titan Guardian" : "Titan"}
      width={Math.round(height * ratio)}
      height={height}
      priority
      className="block flex-none select-none"
      style={{ height, width: "auto" }}
    />
  );
}
