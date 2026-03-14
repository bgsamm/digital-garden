let currentPage = 0;

function prevChannelPage() {
    goToPage(currentPage - 1);
}

function nextChannelPage() {
    goToPage(currentPage + 1);
}

function goToPage(page) {
    const ribbon = document.querySelector('.channel-ribbon');
    const totalPages = ribbon.childElementCount;

    console.log(`From: ${currentPage}, To: ${page}, Out of: ${totalPages}`);

    if (page >= 0 && page < totalPages) {
        currentPage = page;
        ribbon.style.transform = `translateX(-${currentPage * 85}vw)`;
    }
}
