import * as React from "react";

import { cn } from "@/lib/utils";

// Contenedor compartido de página (mejora de interfaz: antes cada pantalla
// armaba su propio <main> a mano, casi idéntico en las cuatro). `wide` es
// la única variación real que hoy necesita alguna pantalla (Grafo, por el
// layout de dos columnas) — no un sistema de tamaños completo.
function PageContainer({
  className,
  wide,
  ...props
}: React.ComponentProps<"main"> & { wide?: boolean }) {
  return (
    <main
      data-slot="page-container"
      className={cn(
        // `h-full` + `overflow-y-auto`: la zona de contenido de App.tsx es de
        // alto fijo (`h-screen`) y `overflow-hidden`; sin esto las pantallas
        // largas (Memoria, Métricas) se recortan sin barra de scroll.
        "mx-auto flex h-full min-h-0 w-full flex-col gap-6 overflow-y-auto px-6 py-10",
        wide ? "max-w-5xl" : "max-w-3xl",
        className,
      )}
      {...props}
    />
  );
}

function PageHeader({
  title,
  description,
  actions,
  className,
  ...props
}: React.ComponentProps<"header"> & {
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <header
      data-slot="page-header"
      className={cn("flex items-start justify-between gap-4", className)}
      {...props}
    >
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="text-muted-foreground text-sm">{description}</p>}
      </div>
      {actions}
    </header>
  );
}

export { PageContainer, PageHeader };
