import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "CrediUCC — Créditos estudiantiles",
  description: "Solicita y consulta tu crédito estudiantil UCC: matrícula, materiales y sostenimiento.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="es" className="h-full antialiased">
      <body className="min-h-full bg-[#f5f7f3] font-sans text-[#1c302c]">{children}</body>
    </html>
  );
}
