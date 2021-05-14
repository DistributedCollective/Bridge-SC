const fs = require('fs');
const {describe, it, beforeEach, afterEach, expect} = global;

const AppendOnlyFileStorage = require("../../src/helpers/AppendOnlyFileStorage");

const storagePath = `${__dirname}`;
const storageFilePath = `${storagePath}/testAppendOnlyFileStorage.txt`;
const nestedStoragePath = `${__dirname}/nested`;
const nestedStorageFilePath = `${nestedStoragePath}/testNestedAppendOnlyFileStorage.txt`;

const cleanUp = () => {
    if (fs.existsSync(storageFilePath)) {
        fs.unlinkSync(storageFilePath);
    }
    if (fs.existsSync(nestedStorageFilePath)) {
        fs.unlinkSync(nestedStorageFilePath);
    }
    if (fs.existsSync(nestedStoragePath)) {
        fs.rmdirSync(nestedStoragePath);
    }
}

describe('AppendOnlyFileStorage module tests', () => {
    let storage;

    beforeEach(() => {
        cleanUp();
        storage = new AppendOnlyFileStorage(storageFilePath);
    });

    afterEach(cleanUp);

    it('should not contain an item initially', () => {
        expect(storage.contains('foo')).toEqual(false);
    });

    it('should contain an item after appending it', () => {
        storage.append('foo');
        expect(storage.contains('foo')).toEqual(true);
    });

    it('should allow appending an item twice', () => {
        storage.append('bar');
        storage.append('bar');
        expect(storage.contains('bar')).toEqual(true);
    });

    it('should allow appending multiple items', () => {
        storage.append('foo');
        storage.append('bar');
        expect(storage.contains('foo')).toEqual(true);
        expect(storage.contains('bar')).toEqual(true);
    });

    it('should write items from file system', () => {
        storage.append('foo');
        storage.append('bar');

        const contents = fs.readFileSync(storageFilePath, 'utf-8');
        expect(contents).toEqual("foo\nbar\n");
    });

    it('should read items from file system', () => {
        fs.writeFileSync(storageFilePath, 'foo\nbar\n', 'utf-8');

        expect(storage.contains('foo')).toEqual(true);
        expect(storage.contains('bar')).toEqual(true);
    });

    it('another storage should read items written by the first', () => {
        storage.append('foo');
        storage.append('bar');

        const newStorage = new AppendOnlyFileStorage(storageFilePath);
        expect(newStorage.contains('foo')).toEqual(true);
        expect(newStorage.contains('bar')).toEqual(true);

        // this case is not 100% supported, because new items are read from memory
        // just have a test for this so it's known
        storage.append('quux');
        expect(newStorage.contains('quux')).toEqual(false);
    });

    it('nested storage should work', () => {
        const nestedStorage = new AppendOnlyFileStorage(nestedStorageFilePath);
        nestedStorage.append('aaa');
        nestedStorage.append('bbb');
        expect(nestedStorage.contains('aaa')).toEqual(true);
        expect(nestedStorage.contains('bbb')).toEqual(true);
    });
});
