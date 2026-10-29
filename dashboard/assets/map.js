window.dashboardMap = Object.assign({}, window.dashboardMap, {
    sectionStyle: function(feature, context) {
        const props = feature.properties || {};
        const hideout = context.hideout || {};
        const colors = hideout.colors || {};
        const selected = hideout.selected === props.k;
        return {
            color: selected ? "#135B75" : (String(props.p).indexOf("EI_") === 0 ? "#8B6B13" : "#FFFFFF"),
            weight: selected ? 3.0 : 0.35,
            opacity: selected ? 1 : 0.58,
            fillColor: colors[props.p] || "#F4F3F1",
            fillOpacity: selected ? 1 : 0.88,
            dashArray: selected ? null : undefined
        };
    },
    sectionPointToLayer: function(feature, latlng, context) {
        const props = feature.properties || {};
        const hideout = (context && context.hideout) || {};
        const colors = hideout.colors || {};
        const selected = hideout.selected === props.k;
        window.dashboardExplorerPointRenderer = window.dashboardExplorerPointRenderer ||
            L.canvas({padding: 0.5, tolerance: 3});
        return L.circleMarker(latlng, {
            renderer: window.dashboardExplorerPointRenderer,
            radius: selected ? 3.6 : 1.55,
            color: selected ? "#135B75" : (String(props.p).indexOf("EI_") === 0 ? "#8B6B13" : colors[props.p] || "#F4F3F1"),
            weight: selected ? 1.4 : 0,
            opacity: selected ? 1 : 0,
            fillColor: colors[props.p] || "#F4F3F1",
            fillOpacity: selected ? 1 : 0.82,
            interactive: true
        });
    },
    profileFilter: function(feature, context) {
        const hideout = context.hideout || {};
        const active = hideout.activeProfiles || [];
        const properties = feature.properties || {};
        const profileAllowed = active.indexOf(properties.p) !== -1;
        if (!profileAllowed) {
            return false;
        }
        if (hideout.densityEnabled) {
            const rank = Number(properties.r);
            if (!(Number.isFinite(rank) && rank > 0 && rank <= Number(hideout.densityLimit || 0))) {
                return false;
            }
        }
        if (hideout.securityEnabled) {
            const securityRank = Number(properties.s);
            if (!(Number.isFinite(securityRank) && securityRank > 0 && securityRank <= Number(hideout.securityLimit || 0))) {
                return false;
            }
        }
        if (hideout.vebEnabled) {
            const attackCount = Number(properties[hideout.vebPeriod === "24m" ? "b" : "a"]);
            if (!(Number.isFinite(attackCount) && attackCount >= 0 && attackCount <= Number(hideout.vebThreshold))) {
                return false;
            }
        }
        return true;
    },
    simulatorFilter: function(feature, context) {
        const hideout = context.hideout || {};
        const props = feature.properties || {};
        const active = hideout.activeProfiles || [];
        if (active.indexOf(props.p) === -1) return false;
        if (!hideout.includeEI && String(props.p).indexOf("EI_") === 0) return false;
        if (hideout.densityEnabled) {
            const rank = Number(props.r);
            if (!(Number.isFinite(rank) && rank > 0 && rank <= Number(hideout.densityLimit || 0))) return false;
        }
        if (hideout.securityEnabled) {
            const rank = Number(props.s);
            if (!(Number.isFinite(rank) && rank > 0 && rank <= Number(hideout.securityLimit || 0))) return false;
        }
        if (hideout.vebEnabled) {
            const count = Number(props[hideout.vebPeriod === "24m" ? "b" : "a"]);
            if (!(Number.isFinite(count) && count >= 0 && count <= Number(hideout.vebThreshold))) return false;
        }
        if (feature.geometry && feature.geometry.type === "Point") {
            return Boolean((hideout.assignmentLookup || {})[String(props.k || "")]);
        }
        return true;
    },
    simulatorSectionStyle: function(feature, context) {
        const props = feature.properties || {};
        const hideout = context.hideout || {};
        const key = String(props.k || "");
        const selected = Boolean((hideout.assignmentLookup || {})[key]);
        const profile = String(props.p || "");
        const priority = (profile === "P1" || profile === "P2") ? "Alta" :
            ((profile === "P4" || profile === "P5") ? "Baja" : "Media");
        const priorityColors = hideout.priorityColors || {};
        const crimeCount = Number(props[hideout.vebPeriod === "24m" ? "b" : "a"]);
        const crimeContext = selected && Number.isFinite(crimeCount) && crimeCount > 0;
        const fillColor = priorityColors[priority] || "#9CA3AF";
        const fillOpacity = selected ? 0.88 : 0;
        return {
            color: crimeContext ? "#343A43" : "#FFFFFF",
            weight: crimeContext ? 0.45 : (selected ? 0.55 : 0),
            opacity: crimeContext ? 0.78 : (selected ? 0.72 : 0),
            fillColor: fillColor,
            fillOpacity: fillOpacity,
            dashArray: crimeContext ? "4 3" : null
        };
    },
    simulatorPointToLayer: function(feature, latlng, context) {
        const props = feature.properties || {};
        const hideout = (context && context.hideout) || {};
        const key = String(props.k || "");
        const selected = Boolean((hideout.assignmentLookup || {})[key]);
        const profile = String(props.p || "");
        const priority = (profile === "P1" || profile === "P2") ? "Alta" :
            ((profile === "P4" || profile === "P5") ? "Baja" : "Media");
        const crimeCount = Number(props[hideout.vebPeriod === "24m" ? "b" : "a"]);
        const crimeContext = selected && Number.isFinite(crimeCount) && crimeCount > 0;
        window.dashboardSimulatorPointRenderer = window.dashboardSimulatorPointRenderer ||
            L.canvas({padding: 0.5, tolerance: 3});
        return L.circleMarker(latlng, {
            renderer: window.dashboardSimulatorPointRenderer,
            radius: selected ? 1.9 : 0,
            color: crimeContext ? "#343A43" : "#FFFFFF",
            weight: crimeContext ? 0.75 : (selected ? 0.35 : 0),
            opacity: selected ? 0.82 : 0,
            fillColor: (hideout.priorityColors || {})[priority] || "#9CA3AF",
            fillOpacity: selected ? 0.9 : 0,
            interactive: selected
        });
    },
    simulatorOnEachFeature: function(feature, layer, context) {
        const props = feature.properties || {};
        const hideout = (context && context.hideout) || {};
        const key = String(props.k || "");
        const profile = String(props.p || "");
        const priority = (profile === "P1" || profile === "P2") ? "Alta" :
            ((profile === "P4" || profile === "P5") ? "Baja" : "Media");
        const assignment = (hideout.assignmentLookup || {})[key];
        const selected = Boolean(assignment);
        const crimeValue = Number(props[hideout.vebPeriod === "24m" ? "b" : "a"]);
        const crimeText = crimeValue >= 0 ? String(crimeValue) : "No disponible";
        let content = props.tooltip || ("<strong>Sección " + key + "</strong><br>Perfil: " + profile);
        content += "<br>Prioridad operativa: " + priority;
        content += "<br>Seleccionada: " + (selected ? "Sí" : "No");
        if (assignment) {
            const names = hideout.interventionNames || {};
            const effects = (hideout.interventionEffects || {})[String(assignment[0])] || [0, 0, 0];
            const base = assignment[1];
            content += "<br>Intervención: " + (names[String(assignment[0])] || "No disponible");
            content += "<br>Sin intervención: " + (base === null ? "No disponible" : Number(base).toFixed(2) + "%");
            if (base !== null) {
                content += "<br>Pesimista: +" + Number(effects[0]).toFixed(2) + " pp → " + Math.min(100, Number(base) + Number(effects[0])).toFixed(2) + "%";
                content += "<br>Normal: +" + Number(effects[1]).toFixed(2) + " pp → " + Math.min(100, Number(base) + Number(effects[1])).toFixed(2) + "%";
                content += "<br>Optimista: +" + Number(effects[2]).toFixed(2) + " pp → " + Math.min(100, Number(base) + Number(effects[2])).toFixed(2) + "%";
            }
        }
        content += "<br>Registros municipales: " + crimeText;
        if (selected && crimeValue > 0) {
            content += "<br><em>Sección seleccionada ubicada en un municipio con registros de crímenes electorales.</em>";
        }
        if (layer && layer.bindTooltip) layer.bindTooltip(content, {sticky: true, direction: "auto"});
    }
});
