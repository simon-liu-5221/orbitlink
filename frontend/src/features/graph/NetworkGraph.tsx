import type { Core, ElementDefinition } from "cytoscape";
import cytoscape from "cytoscape";
import { useEffect, useRef } from "react";

import { communityColor, nodeRadius } from "./graphData";
import type { GraphEdge, GraphNode } from "./graphData";

/**
 * Cytoscape wrapper (PR-10). All the interesting logic — sampling, filtering,
 * color/size encoding — lives in graphData.ts as plain functions; this
 * component just feeds their output to Cytoscape and reports clicks back up.
 */
export function NetworkGraph({
  nodes,
  edges,
  onSelectNode,
  onCyReady,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onSelectNode: (pseudonym: string) => void;
  /** Hands the live Cytoscape instance up (PR-11: "export image" needs cy.png()). */
  onCyReady?: (cy: Core | null) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const maxPagerank = nodes.reduce((max, n) => Math.max(max, n.pagerank), 0);
    const elements: ElementDefinition[] = [
      ...nodes.map((n) => ({
        data: {
          id: n.pseudonym,
          radius: nodeRadius(n.pagerank, maxPagerank),
          color: communityColor(n.community_index),
        },
      })),
      ...edges.map((e) => ({
        data: {
          id: `${e.source}->${e.target}`,
          source: e.source,
          target: e.target,
          weight: e.weight,
        },
      })),
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            width: "data(radius)",
            height: "data(radius)",
            "background-color": "data(color)",
            "border-width": 1,
            "border-color": "#ffffff",
          },
        },
        {
          selector: "edge",
          style: {
            width: 1,
            "line-color": "#cbd5e1",
            "target-arrow-color": "#cbd5e1",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            opacity: 0.6,
          },
        },
      ],
      layout: { name: "cose", animate: false },
    });

    cy.on("tap", "node", (event) => {
      onSelectNode(event.target.id());
    });

    onCyReady?.(cy);

    return () => {
      onCyReady?.(null);
      cy.destroy();
    };
    // onCyReady and onSelectNode are expected to be stable (wrapped in
    // useCallback by the caller); only nodes/edges should re-create the graph.
  }, [nodes, edges, onSelectNode, onCyReady]);

  return (
    <div
      ref={containerRef}
      role="img"
      aria-label="Network graph"
      className="h-[32rem] w-full rounded-lg border border-slate-200 bg-white"
    />
  );
}
