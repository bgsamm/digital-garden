function setView(viewId, updateHistory = true) {
    console.log(`Setting view to '${viewId}'.`);

    const targetView = document.getElementById(`view-${viewId}`);

    if (targetView === null) {
        console.error(`No view with id '${viewId}.`);
    }

    if (targetView.classList.contains('active')) {
        // Already the active view - nothing to do
        return;
    }

    // Remove active class from old tab & view
    const activeView = document.querySelector('.view.active');
    activeView.classList.remove('active');

    const activeTab = document.querySelector('.tab.active');
    activeTab.classList.remove('active')

    // Add active class to new tab & view
    targetView.classList.add('active');

    const targetTab = document.getElementById(`tab-${viewId}`);
    targetTab.classList.add('active');

    if (updateHistory) {
        // Push new view onto browser history
        const newUrl = window.location.pathname + '?view=' + viewId;
        history.pushState({ view: viewId }, '', newUrl);
    }
}

// Respond to browser back/forward buttons
window.onpopstate = function (event) {
    const viewId = (event.state && event.state.view) || 'main';
    setView(viewId, updateHistory = false);
};

// Handle direct links
window.addEventListener('load', () => {
    const params = new URLSearchParams(window.location.search);
    const viewId = params.get('view') || 'main';
    setView(viewId);
});
