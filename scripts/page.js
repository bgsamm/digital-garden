function updateDiffFilter() {
    const value = document.querySelector('input[name="diff-filter"]:checked').value;
    const taskList = document.getElementById('task-list');
    taskList.classList.remove('diff-easy');
    taskList.classList.remove('diff-med');
    taskList.classList.remove('diff-hard');
    taskList.classList.remove('diff-any');
    taskList.classList.add(`diff-${value}`);
}

function updatePrioFilter() {
    const value = document.querySelector('input[name="prio-filter"]:checked').value;
    const taskList = document.getElementById('task-list');
    taskList.classList.remove('prio-low');
    taskList.classList.remove('prio-mid');
    taskList.classList.remove('prio-high');
    taskList.classList.remove('prio-any');
    taskList.classList.add(`prio-${value}`);
}
