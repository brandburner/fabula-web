/* Graph View — extracted from graph_view.html inline <script> */
/* Data injected via <script id="graph-data" type="application/json"> in template */

const graphData = JSON.parse(document.getElementById('graph-data').textContent);
console.log('Graph data loaded:', graphData.nodes.length, 'nodes,', graphData.edges.length, 'edges');
console.log('Sample nodes:', graphData.nodes.slice(0, 3));

// Node type configuration
const NODE_TYPE_CONFIG = {
    'event': { color: '#f59e0b', icon: 'zap', label: 'Event', size: 6 },
    'character': { color: '#14b8a6', icon: 'user', label: 'Character', size: 4 },
    'location': { color: '#84cc16', icon: 'map-pin', label: 'Location', size: 4 },
    'organization': { color: '#a855f7', icon: 'building-2', label: 'Organization', size: 4 },
    'act': { color: '#6366f1', icon: 'bookmark', label: 'Act', size: 8 },
    'plotbeat': { color: '#f472b6', icon: 'activity', label: 'Plot Beat', size: 2 }
};

// Graph Gravity tier configuration for character nodes
const TIER_CONFIG = {
    'anchor': { sizeMultiplier: 4.0, color: '#fbbf24', icon: '\u2600\uFE0F', label: 'Main Cast' },
    'planet': { sizeMultiplier: 1.8, color: '#14b8a6', icon: '\uD83E\uDE90', label: 'Recurring' },
    'asteroid': { sizeMultiplier: 0.6, color: '#6b7280', icon: '\u2604\uFE0F', label: 'One-off' }
};

// Edge type configuration - real LPG relationships
const CONNECTION_CONFIG = {
    // Participation edges (Entity -> Event)
    'PARTICIPATED_AS': { color: '#14b8a6', icon: 'user', label: 'Participates', category: 'participation' },
    'IN_EVENT': { color: '#84cc16', icon: 'map-pin', label: 'In Event', category: 'participation' },
    'INVOLVED_WITH': { color: '#a855f7', icon: 'building-2', label: 'Involved', category: 'participation' },

    // Narrative connections (Event -> Event)
    'CAUSAL': { color: '#22d3ee', icon: 'arrow-right', label: 'Causal', category: 'narrative' },
    'FORESHADOWING': { color: '#a855f7', icon: 'sparkles', label: 'Foreshadowing', category: 'narrative' },
    'THEMATIC_PARALLEL': { color: '#f59e0b', icon: 'git-merge', label: 'Thematic Parallel', category: 'narrative' },
    'CHARACTER_CONTINUITY': { color: '#10b981', icon: 'rotate-ccw', label: 'Character Continuity', category: 'narrative' },
    'ESCALATION': { color: '#ef4444', icon: 'trending-up', label: 'Escalation', category: 'narrative' },
    'CALLBACK': { color: '#3b82f6', icon: 'arrow-left', label: 'Callback', category: 'narrative' },
    'EMOTIONAL_ECHO': { color: '#ec4899', icon: 'heart', label: 'Emotional Echo', category: 'narrative' },
    'SYMBOLIC_PARALLEL': { color: '#8b5cf6', icon: 'equal', label: 'Symbolic Parallel', category: 'narrative' },
    'TEMPORAL': { color: '#6366f1', icon: 'clock', label: 'Temporal', category: 'narrative' },
    'NARRATIVELY_FOLLOWS': { color: '#94a3b8', icon: 'arrow-down', label: 'Narratively Follows', category: 'narrative' },

    // Structural connections (Act/PlotBeat)
    'CONTAINS': { color: '#6366f1', icon: 'bookmark', label: 'Contains', category: 'structural' },
    'DERIVED_FROM': { color: '#f472b6', icon: 'activity', label: 'Derived From', category: 'structural' }
};

// Node type visibility state
const visibleNodeTypes = new Set(['event', 'character', 'location', 'organization', 'act']);

// Transform data for 3d-force-graph (uses 'source'/'target' not 'from'/'to')
const allNodes = graphData.nodes.map(n => ({
    ...n,
    connections: 0,
    visible: true
}));

const allLinks = graphData.edges.map(e => ({
    source: e.from,
    target: e.to,
    type: e.type,
    label: e.label,
    strength: e.strength,
    description: e.description || '',
    pk: e.pk,
    color: CONNECTION_CONFIG[e.type]?.color || '#64748b'
}));

// Count connections per node
const nodeMap = new Map(allNodes.map(n => [n.id, n]));
allLinks.forEach(link => {
    const sourceNode = nodeMap.get(link.source);
    const targetNode = nodeMap.get(link.target);
    if (sourceNode) sourceNode.connections++;
    if (targetNode) targetNode.connections++;
});

// Function to get filtered graph data
function getFilteredGraphData() {
    const visibleNodes = allNodes.filter(n => visibleNodeTypes.has(n.nodeType));
    const visibleNodeIds = new Set(visibleNodes.map(n => n.id));
    const visibleLinks = allLinks.filter(l => {
        const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
        const targetId = typeof l.target === 'object' ? l.target.id : l.target;
        return visibleNodeIds.has(sourceId) && visibleNodeIds.has(targetId);
    });
    return { nodes: visibleNodes, links: visibleLinks };
}

// Initial filtered data
let forceGraphData = getFilteredGraphData();

// Check if pre-computed positions are available (from compute_graph_positions command)
const hasPrecomputedPositions = allNodes.some(n => n.x !== null && n.x !== undefined);

// Update stats display
function updateStats() {
    const data = getFilteredGraphData();
    document.getElementById('node-count').textContent = data.nodes.length;
    document.getElementById('edge-count').textContent = data.links.length;
}
updateStats();

// DOM elements
const container = document.getElementById('graph-container');
const loadingOverlay = document.getElementById('graph-loading');
const tooltip = document.getElementById('graph-tooltip');

// Tooltip elements - nodes
const tooltipNodeIcon = document.getElementById('tooltip-node-icon');
const tooltipNodeType = document.getElementById('tooltip-node-type');
const tooltipNodeTitle = document.getElementById('tooltip-node-title');
const tooltipNodeEpisode = document.getElementById('tooltip-node-episode');
const tooltipNodeLink = document.getElementById('tooltip-node-link');
const tooltipNodeLinkText = document.getElementById('tooltip-node-link-text');

// Tooltip elements - edges
const tooltipEdgeType = document.getElementById('tooltip-edge-type');
const tooltipEdgeDescription = document.getElementById('tooltip-edge-description');
const tooltipEdgeFrom = document.getElementById('tooltip-edge-from');
const tooltipEdgeTo = document.getElementById('tooltip-edge-to');
const tooltipEdgeStrength = document.getElementById('tooltip-edge-strength');
const tooltipEdgeLink = document.getElementById('tooltip-edge-link');

// Mouse position tracking
let mouseX = 0;
let mouseY = 0;
let hideTooltipTimeout = null;
let isMouseOverTooltip = false;

document.addEventListener('mousemove', (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;

    // Update tooltip position if visible
    if (tooltip.classList.contains('visible')) {
        positionTooltip();
    }
});

// Keep tooltip visible when mouse enters it
tooltip.addEventListener('mouseenter', () => {
    isMouseOverTooltip = true;
    if (hideTooltipTimeout) {
        clearTimeout(hideTooltipTimeout);
        hideTooltipTimeout = null;
    }
});

tooltip.addEventListener('mouseleave', () => {
    isMouseOverTooltip = false;
    // Small delay before hiding to allow re-entry
    scheduleHideTooltip(150);
});

function positionTooltip() {
    const tooltipRect = tooltip.getBoundingClientRect();
    const padding = 20;

    // Calculate position - prefer bottom-right of cursor
    let left = mouseX + padding;
    let top = mouseY + padding;

    // Flip to left if would overflow right edge
    if (left + tooltipRect.width > window.innerWidth - padding) {
        left = mouseX - tooltipRect.width - padding;
    }

    // Flip to top if would overflow bottom edge
    if (top + tooltipRect.height > window.innerHeight - padding) {
        top = mouseY - tooltipRect.height - padding;
    }

    // Ensure doesn't go off top or left
    left = Math.max(padding, left);
    top = Math.max(padding, top);

    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
}

// State
let isPaused = false;
let is3D = true;

// Initialize 3d-force-graph
const Graph = ForceGraph3D()(container)
    .graphData(forceGraphData)
    .backgroundColor('rgba(0,0,0,0)')  // Transparent - CSS handles background

    // Node configuration
    .nodeLabel(null)  // We use custom tooltip
    .nodeColor(node => {
        // Characters use tier-based colors
        if (node.nodeType === 'character' && node.tier) {
            const tierConfig = TIER_CONFIG[node.tier];
            if (tierConfig) return tierConfig.color;
        }
        const config = NODE_TYPE_CONFIG[node.nodeType] || { color: '#64748b' };
        return config.color;
    })
    .nodeVal(node => {
        const config = NODE_TYPE_CONFIG[node.nodeType] || { size: 4 };
        let baseSize = config.size;

        // Characters get tier-based size multiplier
        if (node.nodeType === 'character' && node.tier) {
            const tierConfig = TIER_CONFIG[node.tier];
            if (tierConfig) {
                baseSize = config.size * tierConfig.sizeMultiplier;
            }
        }

        // Events are larger, entities scale with connections
        return node.nodeType === 'event'
            ? baseSize + node.connections * 0.5
            : baseSize + node.connections * 0.3;
    })
    .nodeOpacity(0.9)
    // Adaptive resolution based on graph size
    .nodeResolution(forceGraphData.nodes.length > 300 ? 8 : 16)

    // Link configuration - adaptive for performance
    .linkColor(link => link.color)
    .linkWidth(link => {
        // Thinner lines for large graphs
        const scale = forceGraphData.links.length > 1000 ? 0.6 : 1;
        switch(link.strength) {
            case 'strong': return 2 * scale;
            case 'medium': return 1.2 * scale;
            default: return 0.6 * scale;
        }
    })
    .linkOpacity(forceGraphData.links.length > 1000 ? 0.5 : 0.7)
    // Arrows - color must match link color explicitly
    .linkDirectionalArrowLength(forceGraphData.links.length > 500 ? 0 : 4)
    .linkDirectionalArrowRelPos(1)
    .linkDirectionalArrowColor(link => link.color)
    // Straight lines for large graphs (faster)
    .linkCurvature(forceGraphData.links.length > 1000 ? 0 : 0.1)
    // Pulsing particles for small graphs (eye candy but expensive)
    .linkDirectionalParticles(link => {
        if (forceGraphData.links.length > 300) return 0;
        return link.strength === 'strong' ? 2 : 1;
    })
    .linkDirectionalParticleWidth(2)
    .linkDirectionalParticleSpeed(0.008)
    .linkDirectionalParticleColor(link => link.color)

    // Node hover
    .onNodeHover(node => {
        container.style.cursor = node ? 'pointer' : 'default';

        if (node) {
            cancelHideTooltip();
            showNodeTooltip(node);
        } else if (!tooltip.classList.contains('edge-tooltip')) {
            scheduleHideTooltip(200);
        }
    })

    // Node click - navigate to event page
    .onNodeClick(node => {
        if (node && node.url) {
            window.location.href = node.url;
        }
    })

    // Link hover
    .onLinkHover(link => {
        container.style.cursor = link ? 'pointer' : 'default';

        if (link) {
            cancelHideTooltip();
            showEdgeTooltip(link);
        } else if (!tooltip.classList.contains('node-tooltip')) {
            scheduleHideTooltip(200);
        }
    })

    // Link click - navigate to connection detail page
    .onLinkClick(link => {
        if (link && link.pk) {
            window.location.href = `/connections/${link.pk}/`;
        }
    })

    // Performance optimizations - adaptive based on graph size and pre-computed positions
    .warmupTicks(hasPrecomputedPositions ? 20 : (forceGraphData.nodes.length > 300 ? 50 : 100))
    .cooldownTicks(hasPrecomputedPositions ? 50 : (forceGraphData.nodes.length > 300 ? 100 : 200))
    .d3AlphaDecay(forceGraphData.nodes.length > 300 ? 0.04 : 0.02)
    .d3VelocityDecay(forceGraphData.nodes.length > 300 ? 0.4 : 0.3)
    // Enable octree for spatial indexing (O(n log n) vs O(n^2))
    .d3AlphaMin(0.001)
    .enableNodeDrag(true)
    .enableNavigationControls(true);

// Tooltip functions
function showNodeTooltip(node) {
    const config = NODE_TYPE_CONFIG[node.nodeType] || { color: '#64748b', icon: 'circle', label: 'Node' };

    tooltip.classList.add('visible', 'node-tooltip');
    tooltip.classList.remove('edge-tooltip');

    // For characters, use tier-based color
    let nodeColor = config.color;
    if (node.nodeType === 'character' && node.tier) {
        const tierConfig = TIER_CONFIG[node.tier];
        if (tierConfig) nodeColor = tierConfig.color;
    }

    // Set the node color for CSS styling
    tooltip.style.setProperty('--node-color', nodeColor);
    tooltip.style.setProperty('--edge-color', '');

    // Update icon
    tooltipNodeIcon.innerHTML = `<i data-lucide="${config.icon}" class="w-5 h-5"></i>`;

    // Update content - add tier badge for characters
    let typeLabel = config.label;
    if (node.nodeType === 'character' && node.tier) {
        const tierConfig = TIER_CONFIG[node.tier];
        if (tierConfig) {
            typeLabel = `${tierConfig.icon} ${tierConfig.label}`;
        }
    }
    tooltipNodeType.textContent = typeLabel;
    tooltipNodeTitle.textContent = node.fullTitle || node.label;

    // Episode context or tier stats for characters
    if (node.nodeType === 'character' && node.episodeCount) {
        tooltipNodeEpisode.textContent = `${node.episodeCount} episodes, ${node.relationshipCount || 0} relationships`;
    } else {
        tooltipNodeEpisode.textContent = node.episode || '';
    }

    // Update link
    if (node.url) {
        tooltipNodeLink.href = node.url;
        tooltipNodeLink.style.display = 'flex';
        tooltipNodeLinkText.textContent = `View ${config.label.toLowerCase()}`;
    } else {
        tooltipNodeLink.style.display = 'none';
    }

    // Position and render
    positionTooltip();
    lucide.createIcons();
}

function showEdgeTooltip(link) {
    const config = CONNECTION_CONFIG[link.type] || { color: '#64748b', icon: 'link', label: link.type };

    tooltip.classList.add('visible', 'edge-tooltip');
    tooltip.classList.remove('node-tooltip');
    tooltip.style.setProperty('--edge-color', config.color);
    tooltip.style.setProperty('--conn-color', config.color);
    tooltip.style.setProperty('--node-color', '');

    tooltipEdgeType.innerHTML = `<i data-lucide="${config.icon}" class="w-3.5 h-3.5"></i> ${config.label}`;
    tooltipEdgeDescription.textContent = link.description ? `"${link.description}"` : 'No description available';

    // Get node labels (handle both string IDs and object references)
    const sourceNode = typeof link.source === 'object' ? link.source : nodeMap.get(link.source);
    const targetNode = typeof link.target === 'object' ? link.target : nodeMap.get(link.target);

    tooltipEdgeFrom.textContent = sourceNode?.label || link.source;
    tooltipEdgeTo.textContent = targetNode?.label || link.target;
    tooltipEdgeStrength.textContent = `Strength: ${link.strength || 'medium'}`;

    // Update link
    if (link.pk) {
        tooltipEdgeLink.href = `/connections/${link.pk}/`;
        tooltipEdgeLink.style.display = 'flex';
    } else {
        tooltipEdgeLink.style.display = 'none';
    }

    // Position and render
    positionTooltip();
    lucide.createIcons();
}

function hideTooltip() {
    tooltip.classList.remove('visible', 'node-tooltip', 'edge-tooltip');
}

function scheduleHideTooltip(delay = 200) {
    if (isMouseOverTooltip) return;

    if (hideTooltipTimeout) {
        clearTimeout(hideTooltipTimeout);
    }

    hideTooltipTimeout = setTimeout(() => {
        if (!isMouseOverTooltip) {
            hideTooltip();
        }
        hideTooltipTimeout = null;
    }, delay);
}

function cancelHideTooltip() {
    if (hideTooltipTimeout) {
        clearTimeout(hideTooltipTimeout);
        hideTooltipTimeout = null;
    }
}

// Control button handlers
document.getElementById('btn-zoom-in').addEventListener('click', () => {
    const pos = Graph.cameraPosition();
    const factor = 0.7;
    Graph.cameraPosition({
        x: pos.x * factor,
        y: pos.y * factor,
        z: pos.z * factor
    }, null, 300);
});

document.getElementById('btn-zoom-out').addEventListener('click', () => {
    const pos = Graph.cameraPosition();
    const factor = 1.4;
    Graph.cameraPosition({
        x: pos.x * factor,
        y: pos.y * factor,
        z: pos.z * factor
    }, null, 300);
});

document.getElementById('btn-center').addEventListener('click', () => {
    Graph.zoomToFit(400, 50);
});

document.getElementById('btn-pause').addEventListener('click', function() {
    isPaused = !isPaused;
    const icon = this.querySelector('i');

    if (isPaused) {
        Graph.pauseAnimation();
        this.classList.add('active');
        icon.setAttribute('data-lucide', 'play');
    } else {
        Graph.resumeAnimation();
        this.classList.remove('active');
        icon.setAttribute('data-lucide', 'pause');
    }
    lucide.createIcons();
});

document.getElementById('btn-toggle-2d').addEventListener('click', function() {
    is3D = !is3D;

    if (is3D) {
        Graph.numDimensions(3);
        this.classList.remove('active');
        this.innerHTML = '<i data-lucide="box" class="w-5 h-5"></i>';

        if (!performanceMode) {
            Graph
                .nodeResolution(16)
                .linkCurvature(0.1);
        }
    } else {
        Graph.numDimensions(2);
        this.classList.add('active');
        this.innerHTML = '<i data-lucide="square" class="w-5 h-5"></i>';

        Graph
            .nodeResolution(8)
            .linkCurvature(0);

        setTimeout(() => {
            Graph.cameraPosition({ x: 0, y: 0, z: 500 }, { x: 0, y: 0, z: 0 }, 500);
        }, 100);
    }

    lucide.createIcons();
    console.log(`Switched to ${is3D ? '3D' : '2D'} mode`);
});

// Fullscreen toggle
function toggleFullscreen() {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen();
    } else {
        document.exitFullscreen();
    }
}

// Hide loading overlay and fit view after initial layout
Graph.onEngineStop(() => {
    loadingOverlay.classList.add('hidden');
    setTimeout(() => Graph.zoomToFit(400, 50), 100);
});

// Fallback: hide loading after timeout even if simulation doesn't stop
setTimeout(() => {
    loadingOverlay.classList.add('hidden');
}, 3000);

// Handle window resize
window.addEventListener('resize', () => {
    Graph.width(container.clientWidth);
    Graph.height(container.clientHeight);
});

// Initial camera position adjustment for better view
setTimeout(() => {
    Graph.zoomToFit(600, 100);
}, 500);

// Node type toggle handlers
document.querySelectorAll('.node-toggle').forEach(btn => {
    btn.addEventListener('click', function() {
        const nodeType = this.dataset.type;

        if (visibleNodeTypes.has(nodeType)) {
            visibleNodeTypes.delete(nodeType);
            this.classList.remove('active');
        } else {
            visibleNodeTypes.add(nodeType);
            this.classList.add('active');
        }

        // Update graph with filtered data
        const newData = getFilteredGraphData();
        Graph.graphData(newData);
        updateStats();

        lucide.createIcons();
    });
});

// Performance mode toggle
let performanceMode = forceGraphData.nodes.length > 300;
const perfBtn = document.getElementById('btn-performance');

function applyPerformanceMode(enabled) {
    performanceMode = enabled;
    perfBtn.classList.toggle('active', enabled);

    if (enabled) {
        Graph
            .nodeResolution(6)
            .linkOpacity(0.4)
            .linkWidth(0.5)
            .linkDirectionalArrowLength(0)
            .linkDirectionalParticles(0)
            .linkCurvature(0)
            .d3AlphaDecay(0.06)
            .d3VelocityDecay(0.5);
    } else {
        Graph
            .nodeResolution(16)
            .linkOpacity(0.7)
            .linkWidth(link => {
                switch(link.strength) {
                    case 'strong': return 2;
                    case 'medium': return 1.2;
                    default: return 0.6;
                }
            })
            .linkDirectionalArrowLength(4)
            .linkDirectionalParticles(link => link.strength === 'strong' ? 2 : 1)
            .linkCurvature(0.1)
            .d3AlphaDecay(0.02)
            .d3VelocityDecay(0.3);
    }
}

// Auto-enable performance mode for large graphs
if (performanceMode) {
    applyPerformanceMode(true);
    console.log('Performance mode auto-enabled for large graph');
}

// Auto-switch to 2D for very large graphs (massive performance boost)
const autoSwitch2D = allNodes.length > 500 || allLinks.length > 2000;
if (autoSwitch2D) {
    setTimeout(() => {
        const toggle2dBtn = document.getElementById('btn-toggle-2d');
        is3D = false;
        Graph.numDimensions(2);
        toggle2dBtn.classList.add('active');
        toggle2dBtn.innerHTML = '<i data-lucide="square" class="w-5 h-5"></i>';
        Graph.nodeResolution(6).linkCurvature(0);
        lucide.createIcons();
        console.log('2D mode auto-enabled for very large graph');
    }, 100);
}

perfBtn.addEventListener('click', () => {
    applyPerformanceMode(!performanceMode);
    lucide.createIcons();
});

// Legend toggle (mobile)
const legendToggleBtn = document.getElementById('btn-legend');
const legendPanel = document.querySelector('.graph-legend');
if (legendToggleBtn && legendPanel) {
    legendToggleBtn.addEventListener('click', () => {
        legendPanel.classList.toggle('visible');
        legendToggleBtn.classList.toggle('active', legendPanel.classList.contains('visible'));
    });
}

// Log performance stats
console.log(`Graph stats: ${allNodes.length} nodes, ${allLinks.length} edges`);
console.log(`Performance mode: ${performanceMode ? 'ON' : 'OFF'}`);
console.log(`Auto 2D: ${autoSwitch2D ? 'YES' : 'NO'}`);
