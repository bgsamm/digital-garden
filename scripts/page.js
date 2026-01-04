function setView(viewId) {
    const targetView = document.getElementById(`view-${viewId}`);

    if (targetView === null) {
        console.error(`No view with id '${viewId}.`);
    }

    if (targetView.classList.contains('active')) {
        // Already the active view - nothing to do
        return;
    }

    const activeView = document.querySelector('.view.active');
    activeView.classList.remove('active');

    const activeTab = document.querySelector('.tab.active');
    activeTab.classList.remove('active')

    targetView.classList.add('active');

    const targetTab = document.getElementById(`tab-${viewId}`);
    targetTab.classList.add('active');
}
