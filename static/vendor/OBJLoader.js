/**
 * Simple OBJ Loader for Three.js
 * Parses OBJ files and returns a THREE.Group
 */
const OBJLoader = {
    load: function (url, onLoad, onProgress, onError) {
        const loader = new THREE.FileLoader();
        loader.load(url, function (text) {
            try {
                const result = OBJLoader.parse(text);
                if (onLoad) onLoad(result);
            } catch (e) {
                if (onError) onError(e);
                else console.error('OBJLoader error:', e);
            }
        }, onProgress, onError);
    },

    parse: function (text) {
        const object = new THREE.Group();

        const vertices = [];
        const normals = [];
        const uvs = [];

        const vertexData = [];
        const normalData = [];
        const uvData = [];

        function parseVertexIndex(value) {
            const index = parseInt(value);
            return (index >= 0 ? index - 1 : index + vertices.length / 3) * 3;
        }

        function parseNormalIndex(value) {
            const index = parseInt(value);
            return (index >= 0 ? index - 1 : index + normals.length / 3) * 3;
        }

        function parseUVIndex(value) {
            const index = parseInt(value);
            return (index >= 0 ? index - 1 : index + uvs.length / 2) * 2;
        }

        function addVertex(a, b, c) {
            vertexData.push(vertices[a], vertices[a + 1], vertices[a + 2]);
            vertexData.push(vertices[b], vertices[b + 1], vertices[b + 2]);
            vertexData.push(vertices[c], vertices[c + 1], vertices[c + 2]);
        }

        function addNormal(a, b, c) {
            normalData.push(normals[a], normals[a + 1], normals[a + 2]);
            normalData.push(normals[b], normals[b + 1], normals[b + 2]);
            normalData.push(normals[c], normals[c + 1], normals[c + 2]);
        }

        function addUV(a, b, c) {
            uvData.push(uvs[a], uvs[a + 1]);
            uvData.push(uvs[b], uvs[b + 1]);
            uvData.push(uvs[c], uvs[c + 1]);
        }

        function addFace(a, b, c, ua, ub, uc, na, nb, nc) {
            const ia = parseVertexIndex(a);
            const ib = parseVertexIndex(b);
            const ic = parseVertexIndex(c);

            addVertex(ia, ib, ic);

            if (na !== undefined && na !== '') {
                const ina = parseNormalIndex(na);
                const inb = parseNormalIndex(nb);
                const inc = parseNormalIndex(nc);
                addNormal(ina, inb, inc);
            }

            if (ua !== undefined && ua !== '') {
                const iua = parseUVIndex(ua);
                const iub = parseUVIndex(ub);
                const iuc = parseUVIndex(uc);
                addUV(iua, iub, iuc);
            }
        }

        const lines = text.split('\n');

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            if (line.length === 0 || line.charAt(0) === '#') continue;

            const parts = line.split(/\s+/);
            const keyword = parts[0];

            switch (keyword) {
                case 'v':
                    vertices.push(
                        parseFloat(parts[1]),
                        parseFloat(parts[2]),
                        parseFloat(parts[3])
                    );
                    break;

                case 'vn':
                    normals.push(
                        parseFloat(parts[1]),
                        parseFloat(parts[2]),
                        parseFloat(parts[3])
                    );
                    break;

                case 'vt':
                    uvs.push(
                        parseFloat(parts[1]),
                        parseFloat(parts[2])
                    );
                    break;

                case 'f':
                    const faceVertices = parts.slice(1);
                    for (let j = 1; j < faceVertices.length - 1; j++) {
                        const f1 = faceVertices[0].split('/');
                        const f2 = faceVertices[j].split('/');
                        const f3 = faceVertices[j + 1].split('/');

                        addFace(
                            f1[0], f2[0], f3[0],
                            f1[1], f2[1], f3[1],
                            f1[2], f2[2], f3[2]
                        );
                    }
                    break;
            }
        }

        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertexData, 3));

        if (normalData.length > 0) {
            geometry.setAttribute('normal', new THREE.Float32BufferAttribute(normalData, 3));
        } else {
            geometry.computeVertexNormals();
        }

        if (uvData.length > 0) {
            geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvData, 2));
        }

        const material = new THREE.MeshPhongMaterial({
            color: 0xffffff,
            specular: 0x444444,
            shininess: 30
        });
        const mesh = new THREE.Mesh(geometry, material);
        object.add(mesh);

        return object;
    }
};

// Make globally accessible
window.OBJLoader = OBJLoader;
