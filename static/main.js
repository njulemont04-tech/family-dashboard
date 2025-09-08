// This function will run when the entire HTML document has been loaded.
document.addEventListener("DOMContentLoaded", () => {
  // --- START: WEBSOCKET SETUP ---
  const socket = io();

  // Helper function to create the HTML for a new list item
  function createItemElement(listId, item) {
    const li = document.createElement("li");
    li.className = `list-group-item d-flex justify-content-between align-items-center ${
      item.done ? "done" : ""
    }`;
    li.id = `item-${item.id}`;
    li.dataset.itemId = item.id;

    const itemText = document.createElement("span");
    itemText.className = "item-text";
    itemText.textContent = item.text;
    li.appendChild(itemText);

    const buttonGroup = document.createElement("div");

    const toggleForm = document.createElement("form");
    toggleForm.action = "/toggle";
    toggleForm.method = "POST";
    toggleForm.className = "d-inline";
    toggleForm.dataset.itemId = item.id;
    toggleForm.innerHTML = `<input type="hidden" name="item_to_toggle" value="${item.id}"><button type="submit" class="btn btn-sm btn-success me-1">✓</button>`;

    const deleteForm = document.createElement("form");
    deleteForm.action = "/delete";
    deleteForm.method = "POST";
    deleteForm.className = "d-inline";
    deleteForm.dataset.itemId = item.id;
    deleteForm.innerHTML = `<input type="hidden" name="item_to_delete" value="${item.id}"><button type="submit" class="btn btn-sm btn-danger">X</button>`;

    buttonGroup.appendChild(toggleForm);
    buttonGroup.appendChild(deleteForm);
    li.appendChild(buttonGroup);

    return li;
  }

  // Helper function to create the HTML for a new bulletin board note
  function createNoteElement(note) {
    const noteCard = document.createElement("div");
    noteCard.id = `note-${note.id}`;
    noteCard.className = "card mb-3";

    let deleteFormHTML = "";
    // The global 'currentUserId' variable is set in the bulletin_board.html template
    if (
      typeof currentUserId !== "undefined" &&
      currentUserId === note.author_id
    ) {
      deleteFormHTML = `
            <form action="/delete_note" method="POST" class="note-delete-form" data-note-id="${note.id}">
                <input type="hidden" name="note_id" value="${note.id}">
                <button type="submit" class="btn-close" aria-label="Delete"></button>
            </form>
        `;
    }

    noteCard.innerHTML = `
      <div class="card-body d-flex justify-content-between">
        <div>
          <p class="card-text fs-5">${note.content}</p>
          <p class="card-subtitle text-muted" style="font-size: 0.8rem;">
            Posted by <strong>${note.author}</strong> on ${note.timestamp}
          </p>
        </div>
        ${deleteFormHTML}
      </div>
    `;
    return noteCard;
  }

  // When the connection is established
  socket.on("connect", () => {
    console.log("Connected to server!");
    // Find all list containers on the page and join their rooms
    document.querySelectorAll(".list-group[data-list-id]").forEach((list) => {
      const listId = list.dataset.listId;
      socket.emit("join", { list_id: listId });
      console.log(`Joined room for list ${listId}`);
    });
  });

  // Listen for 'item_added' event for lists
  socket.on("item_added", (data) => {
    console.log("Item added event received:", data);
    if (!document.getElementById(`item-${data.item.id}`)) {
      const listElement = document.getElementById(`items-list-${data.list_id}`);
      if (listElement) {
        const newItemElement = createItemElement(data.list_id, data.item);
        listElement.appendChild(newItemElement);

        // --- ADD THIS LINE ---
        newItemElement.classList.add("item-flash");

        attachFormListeners(newItemElement);
      }
    }
  });

  // Listen for 'item_deleted' event for lists
  socket.on("item_deleted", (data) => {
    console.log("Item deleted event received:", data);
    const itemElement = document.getElementById(`item-${data.item_id}`);
    if (itemElement) {
      itemElement.remove();
    }
  });

  // Listen for 'item_toggled' event for lists
  socket.on("item_toggled", (data) => {
    console.log("Item toggled event received:", data);
    const itemElement = document.getElementById(`item-${data.item_id}`);
    if (itemElement) {
      itemElement.classList.toggle("done", data.done_status);
    }
  });

  // --- START: NEW BULLETIN BOARD LISTENERS ---
  socket.on("note_added", (data) => {
    console.log("Note added event received:", data);
    const notesList = document.getElementById("notes-list");
    // Check if the element already exists to avoid duplicates for the acting user
    if (notesList && !document.getElementById(`note-${data.note.id}`)) {
      const newNoteElement = createNoteElement(data.note);
      notesList.prepend(newNoteElement); // Add new notes to the top

      // --- ADD THIS LINE ---
      newNoteElement.classList.add("item-flash");

      attachFormListeners(newNoteElement); // Attach listeners to the new delete form
    }
  });

  socket.on("note_deleted", (data) => {
    console.log("Note deleted event received:", data);
    const noteElement = document.getElementById(`note-${data.note_id}`);
    if (noteElement) {
      noteElement.remove();
    }
  });
  // --- END: NEW BULLETIN BOARD LISTENERS ---

  // --- START: AJAX-IFY ALL THE FORMS ---
  const handleFormSubmit = async (form, callback) => {
    event.preventDefault();
    try {
      const formData = new FormData(form);
      const response = await fetch(form.action, {
        method: "POST",
        body: formData,
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      if (data.success) {
        callback(form, data);
      } else {
        console.error("Server reported an error:", data.message);
      }
    } catch (error) {
      console.error("Error submitting form:", error);
    }
  };

  const handleAddItem = (form, data) => {
    const listId = form.querySelector('[name="list_id"]').value;
    const listElement = document.getElementById(`items-list-${listId}`);
    if (!document.getElementById(`item-${data.item.id}`)) {
      const newItemElement = createItemElement(listId, data.item);
      listElement.appendChild(newItemElement);
      attachFormListeners(newItemElement);
    }
    form.reset();
  };

  const handleDeleteItem = (form, data) => {
    const itemId = form.dataset.itemId;
    document.getElementById(`item-${itemId}`).remove();
  };

  const handleToggleItem = (form, data) => {
    const itemId = form.dataset.itemId;
    document
      .getElementById(`item-${itemId}`)
      .classList.toggle("done", data.done_status);
  };

  const handleAddEvent = (form, data) => {
    const eventList = document.querySelector(".list-group.calendar-events");
    const newEvent = data.event;
    const eventElement = document.createElement("li");
    eventElement.id = `event-${newEvent.id}`;
    eventElement.className =
      "list-group-item d-flex justify-content-between align-items-center";
    eventElement.innerHTML = `
          <div>
              <div class="fw-bold">${newEvent.title}</div>
              <small class="text-muted">${newEvent.formatted_date} at ${newEvent.formatted_time}</small>
          </div>
          <form action="/delete_event" method="POST" class="d-inline event-delete-form" data-event-id="${newEvent.id}">
              <input type="hidden" name="event_id" value="${newEvent.id}">
              <button type="submit" class="btn-close" aria-label="Delete"></button>
          </form>
      `;
    eventList.appendChild(eventElement);
    attachFormListeners(eventElement);
    form.reset();
  };

  const handleDeleteEvent = (form, data) => {
    const eventId = form.dataset.eventId;
    document.getElementById(`event-${eventId}`).remove();
  };

  const handleAddMeal = (form, data) => {
    const day = form.querySelector('[name="day"]').value;
    const mealType = form.querySelector('[name="meal_type"]').value;
    const cellId = `meal-${day}-${mealType}`;
    const cell = document.getElementById(cellId);
    const meal = data.meal;
    if (cell) {
      const mealContent = document.createElement("div");
      mealContent.className = "meal-content";
      mealContent.id = `meal-content-${meal.id}`;
      mealContent.innerHTML = `
          <span>${meal.description}</span>
          <form action="/delete_meal" method="POST" class="meal-delete-form d-inline" data-meal-id="${meal.id}">
            <input type="hidden" name="meal_id" value="${meal.id}">
            <button type="submit" class="btn-close btn-sm" aria-label="Delete"></button>
          </form>
        `;
      cell.innerHTML = "";
      cell.appendChild(mealContent);
      attachFormListeners(cell);
    }
    form.reset();
  };

  const handleDeleteMeal = (form, data) => {
    const mealId = form.dataset.mealId;
    const mealContent = document.getElementById(`meal-content-${mealId}`);
    if (mealContent) {
      mealContent.parentElement.innerHTML = "";
    }
  };

  // Callback for bulletin board notes
  const handleAddNote = (form, data) => {
    const notesList = document.getElementById("notes-list");
    // The WebSocket listener will handle adding the note for all users, including this one.
    // We just need to make sure our own AJAX call doesn't *also* add it, causing a duplicate.
    // The check inside the socket.on('note_added') listener already prevents this.
    // So, we just reset the form.
    if (notesList && !document.getElementById(`note-${data.note.id}`)) {
      const newNoteElement = createNoteElement(data.note);
      notesList.prepend(newNoteElement);
      attachFormListeners(newNoteElement);
    }
    form.reset();
  };

  const handleDeleteNote = (form, data) => {
    const noteId = form.dataset.noteId;
    document.getElementById(`note-${noteId}`).remove();
  };

  const attachFormListeners = (parentElement) => {
    parentElement = parentElement || document;
    parentElement
      .querySelectorAll(".item-add-form")
      .forEach((form) =>
        form.addEventListener("submit", (e) =>
          handleFormSubmit(form, handleAddItem)
        )
      );
    parentElement
      .querySelectorAll('form[action="/delete"]')
      .forEach((form) =>
        form.addEventListener("submit", (e) =>
          handleFormSubmit(form, handleDeleteItem)
        )
      );
    parentElement
      .querySelectorAll('form[action="/toggle"]')
      .forEach((form) =>
        form.addEventListener("submit", (e) =>
          handleFormSubmit(form, handleToggleItem)
        )
      );
    parentElement
      .querySelectorAll(".event-add-form")
      .forEach((form) =>
        form.addEventListener("submit", (e) =>
          handleFormSubmit(form, handleAddEvent)
        )
      );
    parentElement
      .querySelectorAll(".event-delete-form")
      .forEach((form) =>
        form.addEventListener("submit", (e) =>
          handleFormListeners(form, handleDeleteEvent)
        )
      );
    parentElement
      .querySelectorAll(".meal-add-form")
      .forEach((form) =>
        form.addEventListener("submit", (e) =>
          handleFormSubmit(form, handleAddMeal)
        )
      );
    parentElement
      .querySelectorAll(".meal-delete-form")
      .forEach((form) =>
        form.addEventListener("submit", (e) =>
          handleFormSubmit(form, handleDeleteMeal)
        )
      );
    parentElement
      .querySelectorAll(".note-add-form")
      .forEach((form) =>
        form.addEventListener("submit", (e) =>
          handleFormSubmit(form, handleAddNote)
        )
      );
    parentElement
      .querySelectorAll(".note-delete-form")
      .forEach((form) =>
        form.addEventListener("submit", (e) =>
          handleFormSubmit(form, handleDeleteNote)
        )
      );
  };

  // Initial call to attach listeners to all forms on the page
  attachFormListeners();
});
