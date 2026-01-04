function setView(viewId, updateHistory = true) {
    let targetView = null;
    let errorMsg = '';

    if (viewId) {
        targetView = document.getElementById(`view-${viewId}`);
        errorMsg = `No view with id '${viewId}'`;
    }
    else {
        targetView = document.querySelector('.view.default');
        errorMsg = 'No default view';
    }

    if (!targetView) {
        console.error(`Unable to set view: ${errorMsg}.`);
        return;
    }

    // Update view ID in case of using default view
    viewId = targetView.dataset.viewId;

    if (targetView.classList.contains('active')) {
        // Already the active view - nothing to do
        return;
    }

    // Remove active class from old tab & view
    const activeView = document.querySelector('.view.active');
    activeView?.classList.remove('active');

    const activeTab = document.querySelector('.tab.active');
    activeTab?.classList.remove('active')

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
    const viewId = (event.state && event.state.view);
    setView(viewId, updateHistory = false);
};

// Handle direct links
window.addEventListener('load', () => {
    const params = new URLSearchParams(window.location.search);
    const viewId = params.get('view');
    setView(viewId);
});
