window.dashboardMap = Object.assign({}, window.dashboardMap, {
    sectionStyle: function(feature, context) {
        const props = feature.properties || {};
        const hideout = context.hideout || {};
        const colors = hideout.colors || {};
        const selected = hideout.selected === props.k;
        return {
            color: selected ? "#135B75" : (props.p === "EI" ? "#C9C5C0" : "#FFFFFF"),
            weight: selected ? 3.0 : 0.35,
            opacity: selected ? 1 : 0.58,
            fillColor: colors[props.p] || "#F4F3F1",
            fillOpacity: selected ? 1 : 0.88,
            dashArray: selected ? null : undefined
        };
    },
    profileFilter: function(feature, context) {
        const active = (context.hideout || {}).activeProfiles || [];
        return active.indexOf((feature.properties || {}).p) !== -1;
    }
});
