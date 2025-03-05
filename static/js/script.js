document.addEventListener('DOMContentLoaded', function () {
    // Only initialize the graph if the element exists
    const graphContainer = document.getElementById('git-graph');
    if (graphContainer) {
        initGitGraph();
    }

    function openhome(){
        window.location.href = '/';
    }

    function refreshpage(){
        window.location.href = '/gitmain';
    }

    const opengit = document.createElement('button');
    opengit.textContent = 'Home';
    opengit.style.position = 'fixed';
    opengit.style.top = '60px';
    opengit.style.right = '70px';
    opengit.style.padding = '8px 16px';
    opengit.style.background = 'linear-gradient(45deg, #6366f1, #10b981)';
    opengit.style.color = 'white';
    opengit.style.border = 'none';
    opengit.style.borderRadius = '4px';
    opengit.style.cursor = 'pointer';
    opengit.style.zIndex = '1000';

    const refresh = document.createElement('button');
    refresh.textContent = 'Refesh';
    refresh.style.position = 'fixed';
    refresh.style.top = '60px';
    refresh.style.right = '170px';
    refresh.style.padding = '8px 16px';
    refresh.style.background = 'white';
    refresh.style.color = 'black';
    refresh.style.border = '1px solid gray';
    refresh.style.borderRadius = '4px';
    refresh.style.cursor = 'pointer';
    refresh.style.zIndex = '1000';

    refresh.addEventListener('click', refreshpage);
    document.body.appendChild(refresh);

    opengit.addEventListener('click', openhome);
    document.body.appendChild(opengit);
});

function initGitGraph() {
    // Get graph data from the server
    fetch('/get_git_graph')
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error('Error loading graph data:', data.error);
                return;
            }

            if (!data.nodes || data.nodes.length === 0) {
                document.getElementById('git-graph').innerHTML = '<div class="empty-state">No commits to display.</div>';
                return;
            }

            createGraph(data);
        })
        .catch(error => {
            console.error('Error fetching graph data:', error);
        });
}

function createGraph(data) {
    // Set up dimensions and margins
    const container = document.getElementById('git-graph');
    const width = container.clientWidth;
    const height = container.clientHeight;
    const margin = { top: 20, right: 30, bottom: 30, left: 40 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    // Create SVG
    const svg = d3.select('#git-graph')
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    // Create main group and apply transforms
    const g = svg.append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);

    // Process nodes and links for D3 force simulation
    const nodes = data.nodes.map(node => ({ ...node }));
    const links = data.links.map(link => ({ ...link }));

    // Create force simulation
    const simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).id(d => d.id).distance(70))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(innerWidth / 2, innerHeight / 2))
        .force('x', d3.forceX(innerWidth / 2).strength(0.1))
        .force('y', d3.forceY(innerHeight / 2).strength(0.1));

    // Create links
    const link = g.append('g')
        .attr('class', 'links')
        .selectAll('line')
        .data(links)
        .enter()
        .append('line')
        .attr('stroke', '#aaa')
        .attr('stroke-width', 2);

    // Create nodes
    const node = g.append('g')
        .attr('class', 'nodes')
        .selectAll('g')
        .data(nodes)
        .enter()
        .append('g')
        .call(d3.drag()
            .on('start', dragstarted)
            .on('drag', dragged)
            .on('end', dragended));

    // Add circles to nodes
    node.append('circle')
        .attr('r', 10)
        .attr('fill', '#4a6ee0');

    // Add commit short hash text to nodes
    node.append('text')
        .attr('dx', 15)
        .attr('dy', 4)
        .attr('class', 'node-hash')
        .style('font-family', 'monospace')
        .style('font-size', '12px')
        .text(d => d.id.substring(0, 7));

    // Add commit message text to nodes
    node.append('text')
        .attr('dx', 60)
        .attr('dy', 4)
        .attr('class', 'node-message')
        .style('font-size', '11px')
        .text(d => {
            // Truncate message if too long
            return d.message.length > 30 ? d.message.substring(0, 30) + '...' : d.message;
        });

    // Add tooltips
    node.append('title')
        .text(d => `${d.id.substring(0, 7)}: ${d.message}`);

    // Update positions on each tick of the simulation
    simulation.on('tick', () => {
        link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);

        node.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    // Drag functions
    function dragstarted(event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }

    function dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }

    function dragended(event, d) {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }

    // Zoom functionality
    const zoom = d3.zoom()
        .scaleExtent([0.5, 4])
        .on('zoom', zoomed);

    svg.call(zoom);

    function zoomed(event) {
        g.attr('transform', event.transform);
    }
}