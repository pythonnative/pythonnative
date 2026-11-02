// `Pickers` in the browser preview, on `<input type=file>`.

/** The file is the page's, so its `path` is a blob URL. */
function record(file) {
  return { path: URL.createObjectURL(file), name: file.name, mime_type: file.type || "application/octet-stream", size: file.size };
}

/**
 * Browsers open the chooser only during the press that caused it, which the
 * round trip through Python normally stays within. A later call just never
 * opens, and neither that nor a cancel fires any event in every browser.
 */
function choose({ accept, multiple, limit }) {
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.hidden = true;
    if (accept) input.accept = accept;
    input.multiple = multiple;
    const finish = (files) => {
      input.remove();
      resolve(files);
    };
    input.addEventListener("change", () => {
      const files = [...input.files].map(record);
      finish(limit > 0 ? files.slice(0, limit) : files);
    });
    input.addEventListener("cancel", () => finish([]));
    document.body.appendChild(input);
    input.click();
  });
}

export function modules() {
  return {
    Pickers: {
      pick_images({ limit }) {
        return choose({ accept: "image/*", multiple: limit !== 1, limit });
      },
      pick_videos({ limit }) {
        return choose({ accept: "video/*", multiple: limit !== 1, limit });
      },
      pick_documents({ types, multiple }) {
        return choose({ accept: types ? types.join(",") : null, multiple, limit: multiple ? 0 : 1 });
      },
    },
  };
}
