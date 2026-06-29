"use client";
import { useInView } from "@/hooks/useInView";

interface Props {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  direction?: "up" | "left" | "right";
}

export default function RevealSection({
  children,
  className = "",
  delay = 0,
  direction = "up",
}: Props) {
  const { ref, inView } = useInView();

  const translate = {
    up: "translateY(32px)",
    left: "translateX(-32px)",
    right: "translateX(32px)",
  }[direction];

  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? "translate(0,0)" : translate,
        transition: `opacity 0.75s ease ${delay}ms, transform 0.75s ease ${delay}ms`,
      }}
    >
      {children}
    </div>
  );
}
