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
        return true;
    }
});
