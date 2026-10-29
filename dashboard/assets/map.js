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
        if (!(hideout.assignmentLookup || {})[String(props.k || "")]) return false;
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
        return true;
    },
    simulatorParticipationColor: function(value, colors, limits) {
        if (!Number.isFinite(value) || !colors || colors.length !== 5 ||
            !Array.isArray(limits) || limits.length !== 2 ||
            !Number.isFinite(limits[0]) || !Number.isFinite(limits[1])) return "#9CA3AF";
        if (limits[0] === limits[1]) return colors[2];
        const scaled = Math.max(0, Math.min(4, 4 * (value - limits[0]) /
            (limits[1] - limits[0])));
        const index = Math.min(3, Math.floor(scaled));
        const fraction = scaled - index;
        const left = colors[index];
        const right = colors[index + 1];
        if (fraction === 0) return left;
        if (fraction === 1) return right;
        const channel = offset =>
            parseInt(left.slice(offset, offset + 2), 16) * (1 - fraction) +
            parseInt(right.slice(offset, offset + 2), 16) * fraction;
        return "rgb(" + channel(1) + ", " + channel(3) + ", " + channel(5) + ")";
    },
    simulatorSectionStyle: function(feature, context) {
        const props = feature.properties || {};
        const hideout = context.hideout || {};
        const key = String(props.k || "");
        const selected = Boolean((hideout.assignmentLookup || {})[key]);
        const assignment = (hideout.assignmentLookup || {})[key];
        const base = assignment && assignment[1];
        const effects = assignment && (hideout.interventionEffects || {})[String(assignment[0])];
        const centralEffect = effects && Number(effects[1]);
        const participation = base === null || !Number.isFinite(base) ||
            (hideout.mapScenario === "central" && !Number.isFinite(centralEffect))
            ? NaN : (hideout.mapScenario === "central"
                ? Math.min(100, base + centralEffect) : base);
        const crimeCount = Number(props[hideout.vebPeriod === "24m" ? "b" : "a"]);
        const crimeContext = selected && Number.isFinite(crimeCount) && crimeCount > 0;
        const fillColor = window.dashboardMap.simulatorParticipationColor(
            participation, hideout.participationColors, hideout.participationRange
        );
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
                const normal = Math.min(100, Number(base) + Number(effects[1]));
                content += "<br>Normal: +" + (normal - Number(base)).toFixed(2) + " pp → " + normal.toFixed(2) + "%";
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
