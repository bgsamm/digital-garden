function updateDiffFilter(value) {
    const taskList = document.getElementById('task-list');
    taskList.classList.remove('diff-easy');
    taskList.classList.remove('diff-med');
    taskList.classList.remove('diff-hard');
    taskList.classList.remove('diff-any');
    taskList.classList.add(`diff-${value}`);
}
