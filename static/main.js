// This function will run when the entire HTML document has been loaded.
document.addEventListener("DOMContentLoaded", () => {
  // --- START: WEBSOCKET SETUP ---
  // Connect to the WebSocket server
  const socket = io();

  // A function to create the HTML for a new list item
  // This is crucial for creating items that look and act like the server-rendered ones
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

  // Listen for the 'item_added' event from the server
  socket.on("item_added", (data) => {
    console.log("Item added event received:", data);

    // Check if the item element already exists to avoid duplicates from the acting client
    if (!document.getElementById(`item-${data.item.id}`)) {
      const listElement = document.getElementById(`items-list-${data.list_id}`);
      if (listElement) {
        const newItemElement = createItemElement(data.list_id, data.item);
        listElement.appendChild(newItemElement);
        // We need to re-attach event listeners to the new forms
        attachFormListeners(newItemElement);
      }
    }
  });

  // Listen for the 'item_deleted' event
  socket.on("item_deleted", (data) => {
    console.log("Item deleted event received:", data);
    const itemElement = document.getElementById(`item-${data.item_id}`);
    if (itemElement) {
      itemElement.remove();
    }
  });

  // Listen for the 'item_toggled' event
  socket.on("item_toggled", (data) => {
    console.log("Item toggled event received:", data);
    const itemElement = document.getElementById(`item-${data.item_id}`);
    if (itemElement) {
      itemElement.classList.toggle("done", data.done_status);
    }
  });
  // --- END: WEBSOCKET SETUP ---

  // --- START: AJAX-IFY ALL THE FORMS ---
  // This function will be our universal form handler
  const handleFormSubmit = async (form, callback) => {
    // Prevent the default browser form submission
    event.preventDefault();

    try {
      const formData = new FormData(form);
      const response = await fetch(form.action, {
        method: "POST",
        body: formData,
        // This header is crucial for the backend to know it's an AJAX request
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (data.success) {
        // If the request was successful, run the specific callback function
        callback(form, data);
      } else {
        // Handle server-side validation errors (though we don't have any yet)
        console.error("Server reported an error:", data.message);
      }
    } catch (error) {
      console.error("Error submitting form:", error);
    }
  };

  // Callback for adding a list item
  const handleAddItem = (form, data) => {
    const listId = form.querySelector('[name="list_id"]').value;
    const listElement = document.getElementById(`items-list-${listId}`);

    // Check if the element already exists (WebSocket might have added it)
    if (!document.getElementById(`item-${data.item.id}`)) {
      const newItemElement = createItemElement(listId, data.item);
      listElement.appendChild(newItemElement);
      // Attach listeners to the new item's buttons
      attachFormListeners(newItemElement);
    }

    form.reset(); // Clear the input field
  };

  // Callback for deleting a list item
  const handleDeleteItem = (form, data) => {
    const itemId = form.dataset.itemId;
    document.getElementById(`item-${itemId}`).remove();
  };

  // Callback for toggling a list item
  const handleToggleItem = (form, data) => {
    const itemId = form.dataset.itemId;
    const itemElement = document.getElementById(`item-${itemId}`);
    itemElement.classList.toggle("done", data.done_status);
  };

  // Callback for adding an event to the calendar
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
    attachFormListeners(eventElement); // Re-attach listener to the new form
    form.reset();
  };

  const handleDeleteEvent = (form, data) => {
    const eventId = form.dataset.eventId;
    document.getElementById(`event-${eventId}`).remove();
  };

  // Callback for meals
  const handleAddMeal = (form, data) => {
    const day = form.querySelector('[name="day"]').value;
    const mealType = form.querySelector('[name="meal_type"]').value;
    const cellId = `meal-${day}-${mealType}`;
    const cell = document.getElementById(cellId);
    const meal = data.meal;

    if (cell) {
      // Create the inner div that holds the description and delete button
      const mealContent = document.createElement("div");
      mealContent.className = "meal-content";
      mealContent.id = `meal-content-${meal.id}`;

      const descriptionSpan = document.createElement("span");
      descriptionSpan.textContent = meal.description;

      const deleteForm = document.createElement("form");
      deleteForm.action = "/delete_meal";
      deleteForm.method = "POST";
      deleteForm.className = "meal-delete-form d-inline";
      deleteForm.dataset.mealId = meal.id;
      deleteForm.innerHTML = `
          <input type="hidden" name="meal_id" value="${meal.id}">
          <button type="submit" class="btn-close btn-sm" aria-label="Delete"></button>
        `;

      mealContent.appendChild(descriptionSpan);
      mealContent.appendChild(deleteForm);

      // Clear previous content and add the new one
      cell.innerHTML = "";
      cell.appendChild(mealContent);

      // Re-attach listeners to the new form
      attachFormListeners(cell);
    }
    form.reset();
  };

  const handleDeleteMeal = (form, data) => {
    const mealId = form.dataset.mealId;
    const mealContent = document.getElementById(`meal-content-${mealId}`);
    if (mealContent) {
      mealContent.parentElement.innerHTML = ""; // Clear the table cell
    }
  };

  // Callback for bulletin board notes
  const handleAddNote = (form, data) => {
    const notesList = document.getElementById("notes-list");
    const newNote = data.note;

    const noteCard = document.createElement("div");
    noteCard.id = `note-${newNote.id}`;
    noteCard.className = "card mb-3";

    noteCard.innerHTML = `
      <div class="card-body d-flex justify-content-between">
        <div>
          <p class="card-text">${newNote.content}</p>
          <p class="card-subtitle text-muted" style="font-size: 0.8rem;">
            Posted by <strong>${newNote.author}</strong> on ${newNote.timestamp}
          </p>
        </div>
        <form action="/delete_note" method="POST" class="note-delete-form" data-note-id="${newNote.id}">
          <input type="hidden" name="note_id" value="${newNote.id}">
          <button type="submit" class="btn-close" aria-label="Delete"></button>
        </form>
      </div>
    `;

    // Insert the new note at the top of the list
    notesList.prepend(noteCard);

    // Re-attach listeners to the new form
    attachFormListeners(noteCard);

    form.reset();
  };

  const handleDeleteNote = (form, data) => {
    const noteId = form.dataset.noteId;
    document.getElementById(`note-${noteId}`).remove();
  };

  // This function attaches the correct submit handler to each form
  const attachFormListeners = (parentElement) => {
    // If no parentElement is given, default to the whole document
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
          handleFormSubmit(form, handleDeleteEvent)
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
