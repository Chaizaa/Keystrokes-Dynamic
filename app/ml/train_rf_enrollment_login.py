"""
Random Forest training dan evaluation dengan split event_type.

Training dataset: event_type = 'enrollment'
Testing dataset: event_type = 'login'

Untuk setiap user, dilatih model binary classifier (adalah user tersebut atau bukan).
"""

import sqlite3
import pickle
import numpy as np
import json
from pathlib import Path
from typing import Tuple, Dict, List, Any

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    confusion_matrix,
    classification_report,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
)

import matplotlib.pyplot as plt
import seaborn as sns

from app.ml.feature_builder import build_feature_matrix
from app.ml.thresholds import LOW_CONFIDENCE_THRESHOLD
from sklearn.preprocessing import LabelEncoder

def load_samples_by_event_type(db_path: str, event_type: str) -> List[Dict[str, Any]]:
    """Load data dari database berdasarkan event_type."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    cursor = conn.execute(
        """
        SELECT username,
               H_vector,
               DD_vector,
               UD_vector,
               UU_vector,
               DU_vector
        FROM users_vectors
        WHERE event_type = ?
    """,
        (event_type,),
    )

    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return rows


def prepare_features_and_labels(
    rows: List[Dict[str, Any]], target_user: str
) -> Tuple[np.ndarray, np.ndarray]:
    """Build feature matrix dan prepare binary labels."""
    X = build_feature_matrix(rows)

    y = np.array([1 if r["username"] == target_user else 0 for r in rows])

    return X, y


def get_all_users(db_path: str) -> List[str]:
    """Get semua unique usernames dari database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT DISTINCT username FROM users_vectors")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users


def train_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    n_estimators: int = 300,
    max_depth: int = 12,
    min_samples_leaf: int = 5,
) -> RandomForestClassifier:
    """Train Random Forest model."""
    model = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        class_weight="balanced",
        n_jobs=-1,
        random_state=42,
    )

    model.fit(X_train, y_train)
    return model


def evaluate_model(
    model: RandomForestClassifier,
    X_test: np.ndarray,
    y_test: np.ndarray,
    target_user: str,
) -> Dict[str, Any]:
    """Evaluate model dan return metrics."""
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]  # Probability untuk class 1

    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    cm = confusion_matrix(y_test, y_pred)

    return {
        "target_user": target_user,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion_matrix": cm,
        "y_pred": y_pred,
        "y_pred_proba": y_pred_proba,
        "y_test": y_test,
    }

def train_multiclass_model(train_rows):

    print("\nTraining multi-class model...")

    X_train = build_feature_matrix(train_rows)

    usernames = [r["username"] for r in train_rows]

    label_encoder = LabelEncoder()
    y_train = label_encoder.fit_transform(usernames)

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=12,
        min_samples_leaf=5,
        n_jobs=-1,
        random_state=42,
    )

    model.fit(X_train, y_train)

    print(f"[OK] Multi-class model trained for {len(label_encoder.classes_)} users")

    return model, label_encoder

def evaluate_multiclass_model(model, label_encoder, test_rows):

    print("\nEvaluating multi-class model...")

    X_test = build_feature_matrix(test_rows)

    usernames = [r["username"] for r in test_rows]

    y_true = label_encoder.transform(usernames)

    y_pred = model.predict(X_test)

    cm = confusion_matrix(y_true, y_pred)

    accuracy = accuracy_score(y_true, y_pred)

    print(f"[OK] Multi-class accuracy: {accuracy:.4f}")

    return {
        "accuracy": accuracy,
        "confusion_matrix": cm,
        "labels": label_encoder.classes_.tolist(),
        "y_true": y_true.tolist(),
        "y_pred": y_pred.tolist(),
    }


def print_evaluation_report(
    eval_results: List[Dict[str, Any]], save_dir: str = None
) -> None:
    """Print summary evaluation report untuk semua users."""
    print("\n" + "=" * 80)
    print("RANDOM FOREST EVALUATION REPORT")
    print("Training: event_type = 'enrollment'")
    print("Testing: event_type = 'login'")
    print("=" * 80)

    # Summary metrics
    print("\nSUMMARY METRICS:")
    print(f"{'User':<20} {'Accuracy':<12} {'Precision':<12} {'Recall':<12} {'F1-Score':<12}")
    print("-" * 68)

    all_accuracy = []
    all_precision = []
    all_recall = []
    all_f1 = []

    for result in eval_results:
        user = result["target_user"]
        acc = result["accuracy"]
        prec = result["precision"]
        rec = result["recall"]
        f1 = result["f1"]

        print(f"{user:<20} {acc:.4f}        {prec:.4f}       {rec:.4f}       {f1:.4f}")

        all_accuracy.append(acc)
        all_precision.append(prec)
        all_recall.append(rec)
        all_f1.append(f1)

    print("-" * 68)
    print(f"{'AVERAGE':<20} {np.mean(all_accuracy):.4f}        {np.mean(all_precision):.4f}       {np.mean(all_recall):.4f}       {np.mean(all_f1):.4f}")
    print("=" * 80 + "\n")

    # Detailed report per user
    print("\nDETAILED REPORT PER USER:\n")
    for result in eval_results:
        user = result["target_user"]
        cm = result["confusion_matrix"]
        y_test = result["y_test"]
        y_pred = result["y_pred"]

        print(f"\n--- {user} ---")
        print(f"Accuracy:  {result['accuracy']:.4f}")
        print(f"Precision: {result['precision']:.4f}")
        print(f"Recall:    {result['recall']:.4f}")
        print(f"F1-Score:  {result['f1']:.4f}")
        print(f"Test samples: {len(y_test)}")
        print(f"Confusion Matrix:")
        
        # Handle edge cases where confusion matrix might not be 2x2
        if cm.shape[0] == 2 and cm.shape[1] == 2:
            print(f"  TP: {cm[1, 1]}, FP: {cm[0, 1]}")
            print(f"  FN: {cm[1, 0]}, TN: {cm[0, 0]}")
        else:
            print(f"  Shape: {cm.shape}")
            print(f"  Values: {cm}")


def plot_confusion_matrices(
    eval_results: List[Dict[str, Any]], save_dir: str = None
) -> None:
    """Plot confusion matrices untuk semua users."""
    # Filter only results dengan 2x2 confusion matrix
    valid_results = [r for r in eval_results if r["confusion_matrix"].shape == (2, 2)]
    
    if not valid_results:
        print("[WARNING] Tidak ada valid confusion matrices untuk diplot")
        return
    
    n_users = len(valid_results)
    cols = 3
    rows = (n_users + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols, figsize=(15, 5 * rows))
    axes = axes.flatten() if n_users > 1 else [axes]

    for idx, result in enumerate(valid_results):
        cm = result["confusion_matrix"]
        user = result["target_user"]

        sns.heatmap(
            cm,
            annot=True,
            fmt="d",
            cmap="Blues",
            ax=axes[idx],
            xticklabels=["Bukan", "Adalah"],
            yticklabels=["Bukan", "Adalah"],
            cbar=False,
        )
        axes[idx].set_title(f"Confusion Matrix - {user}")
        axes[idx].set_xlabel("Predicted")
        axes[idx].set_ylabel("Actual")

    # Hide empty subplots
    for idx in range(n_users, len(axes)):
        axes[idx].set_visible(False)

    plt.tight_layout()

    if save_dir:
        plot_path = Path(save_dir) / "confusion_matrices.png"
        plt.savefig(plot_path, dpi=100, bbox_inches="tight")
        print(f"[OK] Confusion matrices saved: {plot_path}")

    plt.show()


def plot_metrics_comparison(eval_results: List[Dict[str, Any]], save_dir: str = None):
    """Plot comparison dari semua metrics."""
    users = [r["target_user"] for r in eval_results]
    accuracies = [r["accuracy"] for r in eval_results]
    precisions = [r["precision"] for r in eval_results]
    recalls = [r["recall"] for r in eval_results]
    f1_scores = [r["f1"] for r in eval_results]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Accuracy
    axes[0, 0].bar(users, accuracies, color="skyblue")
    axes[0, 0].set_title("Accuracy per User")
    axes[0, 0].set_ylabel("Accuracy")
    axes[0, 0].set_ylim([0, 1])
    axes[0, 0].tick_params(axis="x", rotation=45)

    # Precision
    axes[0, 1].bar(users, precisions, color="lightgreen")
    axes[0, 1].set_title("Precision per User")
    axes[0, 1].set_ylabel("Precision")
    axes[0, 1].set_ylim([0, 1])
    axes[0, 1].tick_params(axis="x", rotation=45)

    # Recall
    axes[1, 0].bar(users, recalls, color="salmon")
    axes[1, 0].set_title("Recall per User")
    axes[1, 0].set_ylabel("Recall")
    axes[1, 0].set_ylim([0, 1])
    axes[1, 0].tick_params(axis="x", rotation=45)

    # F1 Score
    axes[1, 1].bar(users, f1_scores, color="gold")
    axes[1, 1].set_title("F1-Score per User")
    axes[1, 1].set_ylabel("F1-Score")
    axes[1, 1].set_ylim([0, 1])
    axes[1, 1].tick_params(axis="x", rotation=45)

    plt.tight_layout()

    if save_dir:
        plot_path = Path(save_dir) / "metrics_comparison.png"
        plt.savefig(plot_path, dpi=100, bbox_inches="tight")
        print(f"[OK] Metrics comparison saved: {plot_path}")

    plt.show()


def main(
    db_path: str,
    target_users: List[str] = None,
    output_dir: str = None,
    skip_visualization: bool = False,
):
    """
    Main function untuk training dan evaluation.

    Args:
        db_path: Path ke SQLite database
        target_users: List of users to train. If None, train untuk semua users.
        output_dir: Directory untuk save results dan visualizations
        skip_visualization: Skip plotting jika True
    """

    # Load training data (enrollment)
    print("Loading training data (event_type='enrollment')...")
    train_rows = load_samples_by_event_type(db_path, "enrollment")
    print(f"[OK] Loaded {len(train_rows)} enrollment samples")

    # Load testing data (login)
    print("Loading testing data (event_type='login')...")
    test_rows = load_samples_by_event_type(db_path, "login")
    print(f"[OK] Loaded {len(test_rows)} login samples")

    # Get list of users
    if target_users is None:
        target_users = get_all_users(db_path)
        print(f"Train untuk {len(target_users)} users: {target_users}")

    # Train dan evaluate untuk setiap user
    eval_results = []
    models = {}

    for user_idx, target_user in enumerate(target_users, 1):
        print(f"\n[{user_idx}/{len(target_users)}] Training user: {target_user}")

        # Prepare training data
        X_train, y_train = prepare_features_and_labels(train_rows, target_user)

        if len(X_train) == 0:
            print(f"[WARNING] No training samples untuk user {target_user}, skip...")
            continue

        if np.sum(y_train) == 0:
            print(f"[WARNING] No positive samples (dari user) dalam training data, skip...")
            continue

        print(f"   Training samples: {len(X_train)} ({np.sum(y_train)} dari {target_user})")

        # Train model
        model = train_model(X_train, y_train)

        # Prepare testing data
        X_test, y_test = prepare_features_and_labels(test_rows, target_user)

        if len(X_test) == 0:
            print(f"[WARNING] No testing samples untuk user {target_user}, skip...")
            continue

        print(f"   Testing samples: {len(X_test)} ({np.sum(y_test)} dari {target_user})")

        # Evaluate
        result = evaluate_model(model, X_test, y_test, target_user)
        eval_results.append(result)
        models[target_user] = model

        print(f"   [OK] Accuracy: {result['accuracy']:.4f}, F1: {result['f1']:.4f}")

    # Print evaluation report
    if eval_results:
        print_evaluation_report(eval_results)

        # Save results
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            # Save models
            models_path = output_dir / "rf_models.pkl"
            with open(models_path, "wb") as f:
                pickle.dump(models, f)
            print(f"[OK] Models saved: {models_path}")

            # Save evaluation results
            results_path = output_dir / "evaluation_results.json"
            results_data = {
                user: {
                    "accuracy": result["accuracy"],
                    "precision": result["precision"],
                    "recall": result["recall"],
                    "f1": result["f1"],
                    "confusion_matrix": result["confusion_matrix"].tolist(),
                    "n_test_samples": len(result["y_test"]),
                }
                for user, result in zip(
                    [r["target_user"] for r in eval_results], eval_results
                )
            }
            with open(results_path, "w") as f:
                json.dump(results_data, f, indent=2)
            print(f"[OK] Results saved: {results_path}")
        
                    # =========================
            # MULTI-CLASS TRAINING & SAVE
            # =========================

            multiclass_model, label_encoder = train_multiclass_model(train_rows)

            multiclass_results = evaluate_multiclass_model(
                multiclass_model,
                label_encoder,
                test_rows
            )

            # Save multiclass model
            multiclass_model_path = output_dir / "rf_multiclass_model.pkl"

            with open(multiclass_model_path, "wb") as f:
                pickle.dump({
                    "model": multiclass_model,
                    "label_encoder": label_encoder
                }, f)

            print(f"[OK] Multi-class model saved: {multiclass_model_path}")


            # Save multiclass evaluation JSON
            multiclass_json_path = output_dir / "multiclass_evaluation_results.json"

            with open(multiclass_json_path, "w") as f:
                json.dump({
                    "accuracy": multiclass_results["accuracy"],
                    "labels": multiclass_results["labels"],
                    "confusion_matrix": multiclass_results["confusion_matrix"].tolist()
                }, f, indent=2)

            print(f"[OK] Multi-class evaluation saved: {multiclass_json_path}")
        # Visualizations
        if not skip_visualization:
            print("\nGenerating visualizations...")
            plot_confusion_matrices(eval_results, output_dir)
            plot_metrics_comparison(eval_results, output_dir)

    else:
        print("[ERROR] No users trained successfully!")


if __name__ == "__main__":
    import sys
    from config import Config

    db_path = Config.DATABASE_PATH
    output_dir = "app/ml/results/enrollment_login_split"

    main(db_path, output_dir=output_dir)
