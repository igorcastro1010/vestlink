// product_editor.js - Melhorias Visuais de Cadastro (Upload + Crop + Chips)
document.addEventListener("DOMContentLoaded", () => {
    // -------------------------------------------------------------
    // PARTE 1: CROPPER E DRAG & DROP PARA FOTO PRINCIPAL
    // -------------------------------------------------------------
    const mainImageInput = document.getElementById("id_imagem");
    if (mainImageInput) {
        // Injetar Cropper Modal programaticamente no HTML se não existir
        if (!document.getElementById("cropper-modal")) {
            const modalHtml = `
                <div id="cropper-modal" style="display: none; opacity: 0; position: fixed; z-index: 10000; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(15, 23, 42, 0.7); backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px); align-items: center; justify-content: center; transition: opacity 0.25s ease;">
                    <div style="background-color: var(--surface, #ffffff); margin: auto; padding: 24px; border: 1px solid var(--line, #e5e7eb); border-radius: 16px; width: 90%; max-width: 450px; display: flex; flex-direction: column; gap: 18px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04); transform: scale(0.95); transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);">
                        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--line, #e5e7eb); padding-bottom: 12px;">
                            <strong style="font-size: 1.15rem; color: var(--ink, #111827); font-weight: 800;">Ajustar Foto do Produto</strong>
                            <button type="button" id="close-cropper" style="background: none; border: 0; font-size: 1.6rem; cursor: pointer; color: var(--muted, #4b5563); line-height: 1; transition: color 0.15s;">&times;</button>
                        </div>
                        <div style="width: 100%; max-height: 300px; background-color: #000; overflow: hidden; display: flex; align-items: center; justify-content: center; border-radius: 10px; border: 1px solid rgba(0,0,0,0.1);">
                            <img id="cropper-image" src="" alt="Recortar" style="max-width: 100%; max-height: 300px; display: block;">
                        </div>
                        <div style="display: flex; justify-content: flex-end; gap: 10px; border-top: 1px solid var(--line, #e5e7eb); padding-top: 12px;">
                            <button type="button" id="btn-cancel-crop" style="padding: 10px 18px; font-weight: 700; background: #f3f4f6; color: #111827; border: 1px solid #d1d5db; border-radius: 8px; cursor: pointer; font-size: 0.88rem; transition: all 0.15s;">Cancelar</button>
                            <button type="button" id="btn-confirm-crop" style="padding: 10px 18px; font-weight: 700; background: var(--brand, #5e35b1); color: #fff; border: 0; border-radius: 8px; cursor: pointer; font-size: 0.88rem; transition: all 0.15s; box-shadow: 0 4px 6px -1px rgba(94, 53, 177, 0.2);">Recortar e Aplicar</button>
                        </div>
                    </div>
                </div>
            `;
            document.body.insertAdjacentHTML("beforeend", modalHtml);
        }

        const modal = document.getElementById("cropper-modal");
        const modalContent = modal.querySelector("div");
        const cropperImage = document.getElementById("cropper-image");
        const btnCancel = document.getElementById("btn-cancel-crop");
        const btnConfirm = document.getElementById("btn-confirm-crop");
        const btnClose = document.getElementById("close-cropper");

        let cropper = null;
        let originalFile = null;

        // Criar elemento de Drag & Drop
        const dropzone = document.createElement("div");
        dropzone.className = "drag-drop-zone";
        dropzone.style.cssText = `
            border: 2px dashed var(--line, #e5e7eb);
            border-radius: 12px;
            padding: 30px 24px;
            text-align: center;
            cursor: pointer;
            background: var(--surface, #ffffff);
            background-image: radial-gradient(var(--line, #e7e1dc) 1px, transparent 1px);
            background-size: 14px 14px;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            margin-bottom: 15px;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 10px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.02);
        `;
        dropzone.innerHTML = `
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--brand, #5e35b1); opacity: 0.85; transition: transform 0.2s;">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <circle cx="8.5" cy="8.5" r="1.5"></circle>
                <polyline points="21 15 16 10 5 21"></polyline>
            </svg>
            <span style="font-weight: 800; font-size: 0.95rem; color: var(--ink, #111827);">Foto Principal do Produto (Proporção 1:1)</span>
            <span style="font-size: 0.75rem; color: var(--muted, #4b5563);">Arraste uma foto aqui ou clique para selecionar</span>
        `;

        mainImageInput.parentNode.insertBefore(dropzone, mainImageInput);
        mainImageInput.style.display = "none"; // Esconde input real

        const preventDefaults = (e) => {
            e.preventDefault();
            e.stopPropagation();
        };

        // Efeitos de Drag-over e hover
        ["dragenter", "dragover"].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                preventDefaults(e);
                dropzone.style.borderColor = "var(--brand, #5e35b1)";
                dropzone.style.boxShadow = "0 0 15px rgba(94, 53, 177, 0.2)";
                dropzone.style.transform = "scale(1.01)";
                dropzone.style.backgroundColor = "rgba(94, 53, 177, 0.03)";
                const svg = dropzone.querySelector("svg");
                if (svg) svg.style.transform = "scale(1.1)";
            });
        });

        ["dragleave", "drop"].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                preventDefaults(e);
                dropzone.style.borderColor = "var(--line, #e5e7eb)";
                dropzone.style.boxShadow = "none";
                dropzone.style.transform = "scale(1)";
                dropzone.style.backgroundColor = "var(--surface, #ffffff)";
                const svg = dropzone.querySelector("svg");
                if (svg) svg.style.transform = "scale(1)";
            });
        });

        // Hover simples quando não está arrastando
        dropzone.addEventListener("mouseenter", () => {
            dropzone.style.borderColor = "var(--brand, #5e35b1)";
            dropzone.style.boxShadow = "0 4px 12px rgba(0, 0, 0, 0.03)";
            dropzone.style.transform = "translateY(-1px)";
        });
        dropzone.addEventListener("mouseleave", () => {
            dropzone.style.borderColor = "var(--line, #e5e7eb)";
            dropzone.style.boxShadow = "none";
            dropzone.style.transform = "translateY(0)";
        });

        // Efeitos hover nos botões do modal
        [btnCancel, btnClose].forEach(btn => {
            btn.addEventListener("mouseenter", () => btn.style.color = "#ef4444");
            btn.addEventListener("mouseleave", () => btn.style.color = "");
        });
        btnConfirm.addEventListener("mouseenter", () => {
            btnConfirm.style.transform = "translateY(-1px)";
            btnConfirm.style.boxShadow = "0 6px 12px rgba(94, 53, 177, 0.35)";
        });
        btnConfirm.addEventListener("mouseleave", () => {
            btnConfirm.style.transform = "translateY(0)";
            btnConfirm.style.boxShadow = "0 4px 6px -1px rgba(94, 53, 177, 0.2)";
        });

        dropzone.addEventListener("click", () => mainImageInput.click());

        const handleFile = (file) => {
            if (!file || !file.type.startsWith("image/")) return;
            originalFile = file;
            const reader = new FileReader();
            reader.onload = (e) => {
                cropperImage.src = e.target.result;
                modal.style.display = "flex";
                // Animação de fade in
                setTimeout(() => {
                    modal.style.opacity = "1";
                    modalContent.style.transform = "scale(1)";
                }, 10);
                
                if (cropper) cropper.destroy();
                cropper = new Cropper(cropperImage, {
                    aspectRatio: 1,
                    viewMode: 1,
                    autoCropArea: 1,
                    responsive: true
                });
            };
            reader.readAsDataURL(file);
        };

        mainImageInput.addEventListener("change", (e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
        });

        dropzone.addEventListener("drop", (e) => {
            const file = e.dataTransfer.files?.[0];
            if (file) handleFile(file);
        });

        const closeAndCleanup = () => {
            modal.style.opacity = "0";
            modalContent.style.transform = "scale(0.95)";
            setTimeout(() => {
                modal.style.display = "none";
                if (cropper) {
                    cropper.destroy();
                    cropper = null;
                }
                mainImageInput.value = "";
            }, 250);
        };

        btnCancel.addEventListener("click", closeAndCleanup);
        btnClose.addEventListener("click", closeAndCleanup);

        btnConfirm.addEventListener("click", () => {
            if (!cropper) return;
            cropper.getCroppedCanvas({
                width: 800,
                height: 800
            }).toBlob((blob) => {
                const fileName = originalFile ? originalFile.name : "produto.jpg";
                const croppedFile = new File([blob], fileName, { type: "image/jpeg" });
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(croppedFile);
                mainImageInput.files = dataTransfer.files;

                // Atualiza pré-visualização de imagem se houver no form
                const previewImage = document.querySelector("[data-preview-image]");
                if (previewImage) {
                    const previewUrl = URL.createObjectURL(blob);
                    previewImage.style.backgroundImage = `url('${previewUrl}')`;
                    previewImage.textContent = "";
                }

                // Renderiza thumbnail de sucesso dentro do dropzone
                const previewUrl = URL.createObjectURL(blob);
                dropzone.innerHTML = `
                    <div style="position: relative; width: 70px; height: 70px; border-radius: 8px; border: 1px solid var(--line, #e5e7eb); background-image: url('${previewUrl}'); background-size: cover; background-position: center; box-shadow: 0 4px 10px rgba(0,0,0,0.08); margin-bottom: 2px;"></div>
                    <span style="font-weight: 800; font-size: 0.9rem; color: #065f46; display: flex; align-items: center; gap: 5px;">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="color: #065f46;">
                            <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                        Foto recortada com sucesso!
                    </span>
                    <span style="font-size: 0.75rem; color: var(--muted, #4b5563);">Clique para alterar a foto principal</span>
                `;

                // Animação suave para fechar o modal
                modal.style.opacity = "0";
                modalContent.style.transform = "scale(0.95)";
                setTimeout(() => {
                    modal.style.display = "none";
                    cropper.destroy();
                    cropper = null;
                }, 250);
            }, "image/jpeg");
        });
    }

    // -------------------------------------------------------------
    // PARTE 2: CHIPS INTERATIVOS PARA GRADE (TAMANHOS E CORES)
    // -------------------------------------------------------------
    const colorMap = {
        "preto": "#18181b",
        "branco": "#ffffff",
        "vermelho": "#ef4444",
        "azul": "#3b82f6",
        "verde": "#10b981",
        "rosa": "#ec4899",
        "cinza": "#6b7280",
        "bege": "#f5f5dc",
        "jeans": "#4f759c"
    };

    const setupTagChips = (inputId, labelText, popularTags) => {
        const input = document.getElementById(inputId);
        if (!input) return;

        input.style.display = "none";
        const isColor = inputId === "id_cores";

        const container = document.createElement("div");
        container.className = "tag-chips-container";
        container.style.cssText = `
            border: 1px solid var(--line, #e5e7eb);
            border-radius: 10px;
            padding: 14px;
            background: var(--surface, #ffffff);
            display: flex;
            flex-direction: column;
            gap: 10px;
            margin-bottom: 18px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.02);
        `;

        container.innerHTML = `
            <span style="font-size: 0.88rem; font-weight: 800; color: var(--ink, #111827);">${labelText}</span>
            <div class="active-chips" style="display: flex; flex-wrap: wrap; gap: 6px;"></div>
            <div style="display: flex; gap: 8px; align-items: center; margin-top: 4px;">
                <input type="text" placeholder="Adicionar personalizado..." style="flex: 1; min-height: 36px; padding: 6px 10px; font-size: 0.85rem; border: 1px solid var(--line, #e5e7eb); border-radius: 8px; background: var(--surface); color: var(--ink);">
                <button type="button" style="min-height: 36px; padding: 6px 14px; font-size: 0.9rem; background: var(--brand, #5e35b1); color: #fff; border: 0; border-radius: 8px; cursor: pointer; font-weight: 800; transition: background 0.15s;">+</button>
            </div>
            <div style="margin-top: 8px; border-top: 1px solid var(--line, #e5e7eb); padding-top: 10px;">
                <span style="font-size: 0.72rem; color: var(--muted, #4b5563); display: block; margin-bottom: 6px; font-weight: 600;">Sugestões populares (clique para ativar):</span>
                <div class="popular-chips" style="display: flex; flex-wrap: wrap; gap: 6px;"></div>
            </div>
        `;

        input.parentNode.insertBefore(container, input);

        const activeContainer = container.querySelector(".active-chips");
        const popularContainer = container.querySelector(".popular-chips");
        const textInput = container.querySelector("input");
        const addButton = container.querySelector("button");

        const getTags = () => input.value.split(",").map(t => t.trim()).filter(Boolean);
        const setTags = (tags) => {
            input.value = tags.join(", ");
            input.dispatchEvent(new Event("input", { bubbles: true }));
            input.dispatchEvent(new Event("change", { bubbles: true }));
            
            // Regeneração automática do estoque se a função de grid existir globalmente (em painel_loja)
            if (typeof window.buildStockGrid === "function") {
                window.buildStockGrid();
            }
        };

        const render = () => {
            const tags = getTags();
            
            activeContainer.innerHTML = tags.map(tag => {
                let colorCircle = "";
                if (isColor) {
                    const colorHex = colorMap[tag.toLowerCase()] || "#cccccc";
                    colorCircle = `<span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background-color: ${colorHex}; border: 1px solid ${tag.toLowerCase() === 'branco' ? '#d1d5db' : 'transparent'}; margin-right: 5px; flex-shrink: 0;"></span>`;
                }
                return `
                    <span class="active-chip-pill" style="display: inline-flex; align-items: center; padding: 5px 10px; font-size: 0.8rem; background: var(--line, #e5e7eb); color: var(--ink, #111827); border-radius: 9999px; font-weight: 700; transition: all 0.15s ease;">
                        ${colorCircle}
                        ${tag}
                        <span class="remove-chip" data-tag="${tag}" style="cursor: pointer; font-weight: 900; margin-left: 5px; color: #6b7280; font-size: 0.95rem; line-height: 1;">&times;</span>
                    </span>
                `;
            }).join("");

            popularContainer.innerHTML = popularTags.map(tag => {
                const isActive = tags.some(t => t.toLowerCase() === tag.toLowerCase());
                let colorCircle = "";
                if (isColor) {
                    const colorHex = colorMap[tag.toLowerCase()] || "#cccccc";
                    colorCircle = `<span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background-color: ${colorHex}; border: 1px solid ${tag.toLowerCase() === 'branco' ? '#d1d5db' : 'transparent'}; margin-right: 5px; flex-shrink: 0;"></span>`;
                }
                return `
                    <span class="popular-chip-pill" data-tag="${tag}" style="cursor: pointer; display: inline-flex; align-items: center; padding: 5px 10px; font-size: 0.75rem; border: 1px solid ${isActive ? "var(--brand, #5e35b1)" : "var(--line, #e5e7eb)"}; background: ${isActive ? "rgba(94, 53, 177, 0.06)" : "var(--surface, #ffffff)"}; color: ${isActive ? "var(--brand, #5e35b1)" : "var(--muted, #4b5563)"}; border-radius: 8px; font-weight: 700; transition: all 0.15s ease; user-select: none;">
                        ${colorCircle}
                        ${isActive ? "✓ " : ""}${tag}
                    </span>
                `;
            }).join("");
        };

        const addTag = (tag) => {
            tag = tag.trim();
            if (!tag) return;
            const tags = getTags();
            if (!tags.some(t => t.toLowerCase() === tag.toLowerCase())) {
                tags.push(tag);
                setTags(tags);
                render();
            }
        };

        const removeTag = (tag) => {
            const tags = getTags().filter(t => t.toLowerCase() !== tag.toLowerCase());
            setTags(tags);
            render();
        };

        activeContainer.addEventListener("click", (e) => {
            const removeBtn = e.target.closest(".remove-chip");
            if (removeBtn) {
                removeTag(removeBtn.dataset.tag);
            }
        });

        popularContainer.addEventListener("click", (e) => {
            const pill = e.target.closest(".popular-chip-pill");
            if (pill) {
                const tag = pill.dataset.tag;
                const tags = getTags();
                if (tags.some(t => t.toLowerCase() === tag.toLowerCase())) {
                    removeTag(tag);
                } else {
                    addTag(tag);
                }
            }
        });

        addButton.addEventListener("click", () => {
            addTag(textInput.value);
            textInput.value = "";
        });

        textInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                addTag(textInput.value);
                textInput.value = "";
            }
        });

        // Hover animações nos botões personalizados
        addButton.addEventListener("mouseenter", () => addButton.style.background = "var(--ink, #111827)");
        addButton.addEventListener("mouseleave", () => addButton.style.background = "");

        render();
    };

    // Inicialização para campos de grade
    setupTagChips("id_tamanhos", "Tamanhos do Produto", ["PP", "P", "M", "G", "GG", "G1", "36", "38", "40", "42", "44", "46"]);
    setupTagChips("id_cores", "Cores do Produto", ["Preto", "Branco", "Vermelho", "Azul", "Verde", "Rosa", "Cinza", "Bege", "Jeans"]);
});
