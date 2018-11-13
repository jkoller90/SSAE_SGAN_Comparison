import click
from tmi import *

@click.group()
def cli():
   pass

@cli.command()
def test_predict():
    # X_test, y_test = load_TMI_test_data()
    X_train, y_train, X_test, y_test = load_TMI_data()

    print ("Loaded test data")
    sgan = SGAN()

    sgan.load_weights()

    sgan.evaluate_discriminator(X_test, y_test)

    sgan.predict(X_test, y_test)

@cli.command()
@click.option('-p', '--path', 
    type=click.Path(exists=True),
    help='Tests the current model against a provided dataset')
def test_model(path):
    print(path)
    sgan = SGAN()
    sgan.load_weights()

    m = mmappickle.mmapdict(path, readonly=True)
    all_preds = None
    all_tests = None
    print(m.keys())
    for key in list(m.keys())[:10]:
        print(key)
        d = m[key]
        crop = d['crop']
        cell = d['cell']
        print(d.keys())

        windows = sliding_windows((400, 400), (34, 34), 6)[:1]
        patches = [crop[w[0]:w[2], w[1]:w[3]] for w in windows]
        cell_patches = [cell[w[0]:w[2], w[1]:w[3]] for w in windows]
        y_test = np.array([is_nuclei(n) for n in cell_patches])
        try:
            y_proba = sgan.predict_proba(prepare_patches(patches))
            print(y_proba)
            y_proba = y_proba[1][:,:-1]
            print(y_proba)
            y_pred = np.argmax(y_proba, axis=1)
            print(y_pred)
        except Exception as e:
            print("Erro")
            continue
        else:
            pass
        return
    #     print(np.argwhere(y_pred == 1))
    #     return
        nuclei_picks = nms(windows, y_proba[:,1], 0.1, 0.3)
        print(nuclei_picks)
    #     print("Nuclei picks")
        non_nuclei_picks  = nms(windows, y_proba[:,0], 0.1, 0.3)
    #     print(nuclei_picks)
    #     print("Non nuclei picks")
    #     print(non_nuclei_picks)
        picks =  np.concatenate((nuclei_picks, non_nuclei_picks))
        print(picks)
    #     print(picks)
        y_test = y_test[picks]
        y_pred = y_pred[picks]

        if all_preds is None:
            all_preds = y_pred
            all_tests = y_test
        else:
            all_preds = np.concatenate((all_preds, y_pred))
            all_tests = np.concatenate((all_tests, y_test))

    print ('\nOverall accuracy: %f%% \n' % (accuracy_score(all_preds, all_tests) * 100))
    print ('\nAveP: %f%% \n' % (average_precision_score(all_preds, all_tests) * 100))
    
    # Calculating and ploting a Classification Report
    class_names = ['Non-nunclei', 'Nuclei']
    print('Classification report:\n %s\n'
          % (classification_report(all_preds, all_tests, target_names=class_names)))

    # Calculating and ploting Confusion Matrix
    # cm = confusion_matrix(all_preds, all_tests)
#        print('Confusion matrix:\n%s' % cm)

    # plt.figure()
    # plot_confusion_matrix(cm, class_names, title='Confusion matrix, without normalization')

    # plt.figure()
    # plot_confusion_matrix(cm, class_names, normalize=True, title='Normalized confusion matrix')


    # sgan.evaluate_discriminator(X_test, y_test)
    # sgan.predict(X_test, y_test)

@cli.command()
@click.option('-d', type=click.Path(exists=True),
    help='Directory to read images from')
@click.option('-n', type=int, default=500,
    help='Number of images in the sample')
@click.option('-o', 'output', default='output',
    help='Output Folder')
def create_dataset(d, n, output):
    prefixes = [d + '/' + p.split('.')[0] for p in os.listdir(d) if '_' not in p and 'tif' in p]
    prefixes = np.random.choice(prefixes, n, replace=False)
    out_path = output + '/out'
    if os.path.isfile(out_path):
        os.remove(out_path)

    m = mmappickle.mmapdict(out_path)
    for prefix in prefixes:
        crop, cells = image_for_prefix(prefix)
        d = {
            'crop': crop,
            'cell': cells
        }

        key = os.path.basename(prefix)
        m[key] = d

if __name__ == '__main__':
    cli()