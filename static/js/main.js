// main.js — общий JS АтлетБазы

document.addEventListener("DOMContentLoaded", function () {
    initParticipantsTable();
    initLecturerSearch();
});

function initLecturerSearch() {
    var searchInput = document.getElementById("lecturer-search-input");
    var searchResults = document.getElementById("lecturer-search-results");
    if (!searchInput || !searchResults) return;

    var timer = null;
    searchInput.addEventListener("input", function () {
        clearTimeout(timer);
        var q = searchInput.value.trim();
        if (q.length < 2) {
            searchResults.innerHTML = "";
            return;
        }
        timer = setTimeout(function () {
            fetch("/judges/search?q=" + encodeURIComponent(q))
                .then(function (r) { return r.json(); })
                .then(function (items) {
                    searchResults.innerHTML = "";
                    items.forEach(function (j) {
                        var btn = document.createElement("button");
                        btn.type = "button";
                        btn.className = "list-group-item list-group-item-action";
                        var label = j.full_name;
                        if (j.birth_date) {
                            label += " (" + j.birth_date.split("-").reverse().join(".") + ")";
                        }
                        btn.textContent = label;
                        btn.addEventListener("click", function () {
                            document.getElementById("judge_id").value = j.id;
                            document.getElementById("full_name").value = j.full_name || "";
                            document.getElementById("birth_date").value = j.birth_date || "";
                            document.getElementById("region").value = j.region || "";
                            document.querySelectorAll(".qualification-radio").forEach(function (radio) {
                                radio.checked = j.qualification && radio.value === j.qualification;
                            });
                            searchInput.value = "";
                            searchResults.innerHTML = "";
                        });
                        searchResults.appendChild(btn);
                    });
                });
        }, 250);
    });
}

function initParticipantsTable() {
    var tbody = document.getElementById("participants-tbody");
    var template = document.getElementById("participant-row-template");
    var addBtn = document.getElementById("add-participant-row");
    if (!tbody || !template) return;

    function renumberRows() {
        tbody.querySelectorAll("tr.participant-row").forEach(function (row, i) {
            row.querySelector(".row-index").textContent = i + 1;
        });
    }

    function addRow(prefill) {
        var clone = template.content.firstElementChild.cloneNode(true);
        if (prefill) {
            clone.querySelector(".p-judge-id").value = prefill.judge_id || "";
            clone.querySelector(".p-full-name").value = prefill.full_name || "";
            clone.querySelector(".p-birth-date").value = prefill.birth_date || "";
            clone.querySelector(".p-qualification").value = prefill.qualification || "";
        }
        tbody.appendChild(clone);
        renumberRows();
    }

    tbody.addEventListener("click", function (e) {
        var removeBtn = e.target.closest(".remove-participant-row");
        if (removeBtn) {
            removeBtn.closest("tr").remove();
            renumberRows();
        }
    });

    if (addBtn) {
        addBtn.addEventListener("click", function () {
            addRow(null);
        });
    }

    renumberRows();

    var searchInput = document.getElementById("judge-search-input");
    var searchResults = document.getElementById("judge-search-results");
    if (searchInput && searchResults) {
        var timer = null;
        searchInput.addEventListener("input", function () {
            clearTimeout(timer);
            var q = searchInput.value.trim();
            if (q.length < 2) {
                searchResults.innerHTML = "";
                return;
            }
            timer = setTimeout(function () {
                fetch("/judges/search?q=" + encodeURIComponent(q))
                    .then(function (r) { return r.json(); })
                    .then(function (items) {
                        searchResults.innerHTML = "";
                        items.forEach(function (j) {
                            var btn = document.createElement("button");
                            btn.type = "button";
                            btn.className = "list-group-item list-group-item-action";
                            var label = j.full_name;
                            if (j.birth_date) {
                                label += " (" + j.birth_date.split("-").reverse().join(".") + ")";
                            }
                            btn.textContent = label;
                            btn.addEventListener("click", function () {
                                addRow({
                                    judge_id: j.id,
                                    full_name: j.full_name,
                                    birth_date: j.birth_date,
                                    qualification: j.qualification,
                                });
                                searchInput.value = "";
                                searchResults.innerHTML = "";
                            });
                            searchResults.appendChild(btn);
                        });
                    });
            }, 250);
        });
    }
}
